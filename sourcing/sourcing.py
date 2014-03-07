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
from osv import osv, fields
from tools.translate import _
from tools import misc

import decimal_precision as dp
import threading
import netsvc
import pooler
import time

from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from sale_override import SALE_ORDER_STATE_SELECTION
from osv.orm import browse_record

_SELECTION_PO_CFT = [
                     ('po', 'Purchase Order'),
                     ('dpo', 'Direct Purchase Order'),
                     ('cft', 'Tender'),
                     ('rfq', 'Request for Quotation'),
                     ]


class sale_order(osv.osv):

    _inherit = 'sale.order'
    _description = 'Sales Order'
    # TODO: TO REFACTORE
    _columns = {
                'sourcing_trace_ok': fields.boolean(string='Display sourcing logs'),
                'sourcing_trace': fields.text(string='Sourcing logs', readonly=True),
                }

    # TODO: TO REFACTORE
    def write(self, cr, uid, ids, vals, context=None):
        '''
        _inherit = 'sale.order'

        override to update sourcing_line :
         - priority
         - category
         - order state
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        context['fromOrder'] = True
        context['no_check_line'] = True

        values = {}
        if 'priority' in vals:
            values.update({'priority': vals['priority']})
        if 'categ' in vals:
            values.update({'categ': vals['categ']})

        # UTP-392: If the FO is a Loan, then all lines must be from Stock
        if 'order_type' in vals and vals['order_type'] == 'loan':
            context['loan_type'] = True

        if 'type' in vals:
            values.update({'type': vals['type']})

#        if 'state' in vals:
#            values.update({'sale_order_state': vals['state']})
#        if 'state_hidden_sale_order' in vals:
#            values.update({'sale_order_state': vals['state_hidden_sale_order']})

        if values or vals.get('partner_id'):
            for so in self.browse(cr, uid, ids, context):
                sourcing_values = values.copy()
                if vals.get('partner_id') and vals.get('partner_id') != so.partner_id.id:
                    sourcing_values.update({'customer': so.partner_id.id})

        return super(sale_order, self).write(cr, uid, ids, vals, context)

    # TODO: TO REFACTORE
    def copy(self, cr, uid, order_id, default=None, context=None):
        '''
        copy from sale_order

        dont copy sourcing lines, they are generated at sale order lines creation
        '''
        if not default:
            default = {}

        default['sourcing_trace'] = ''
        default['sourcing_trace_ok'] = False

        return super(sale_order, self).copy(cr, uid, order_id, default, context)

    # TODO: TO REFACTORE
    def action_cancel(self, cr, uid, ids, context=None):
        '''
        Don't check line integrity
        '''
        if not context:
            context = {}

        context.update({'no_check_line': True})

        return super(sale_order, self).action_cancel(cr, uid, ids, context=context)

    # TODO: TO REFACTORE
    def _hook_ship_create_procurement_order(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py

        - allow to modify the data for procurement order creation
        '''
        result = super(sale_order, self)._hook_ship_create_procurement_order(cr, uid, ids, context=context, *args, **kwargs)
        line = kwargs['line']

        # new field representing selected partner from sourcing tool
        result['supplier'] = line.supplier and line.supplier.id or False
        if line.po_cft:
            result.update({'po_cft': line.po_cft})
        # uf-583 - the location defined for the procurementis input instead of stock if the procurement is on order
        # if from stock, the procurement search from products in the default location: Stock
        order = kwargs['order']
        if line.type == 'make_to_order':
            result['location_id'] = order.shop_id.warehouse_id.lot_input_id.id,

        return result

    # TODO: TO REFACTORE
    def _hook_procurement_create_line_condition(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py

        - allow to customize the execution condition
        '''
        line = kwargs['line']
        result = super(sale_order, self)._hook_procurement_create_line_condition(cr, uid, ids, context=context, *args, **kwargs)

        # if make_to_stock and procurement_request, no procurement is created
        return result and not(line.type == 'make_to_stock' and line.order_id.procurement_request)

    # TODO: TO REFACTORE
    def do_order_confirm_method(self, cr, uid, ids, context=None):
        '''
        trigger the workflow
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        wf_service = netsvc.LocalService("workflow")
        sol_obj = self.pool.get('sale.order.line')

        # we confirm (validation in unifield) the sale order
        # we set all line state to 'sourced' of the original Fo
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.order_line:
                sol_obj.write(cr, uid, [line.id], {'state': 'sourced'}, context=context)
            # trigger workflow signal
            wf_service.trg_validate(uid, 'sale.order', obj.id, 'order_confirm', cr)

        return True
        return {'name':_("Field Orders"),
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_model': 'sale.order',
                'res_id': ids[0],
                'type': 'ir.actions.act_window',
                'target': 'dummy',
                'domain': [],
                'context': {},
                }

sale_order()


class sale_order_line(osv.osv):
    """
    override of sale_order_line class
    creation/update/copy of sourcing_line
    """
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'

    """
    Generic methods
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

    """
    Methods to get fields.function values
    """
    def _get_fake(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for i in ids:
            res[i] = False

        return res

    def _get_sale_order_state(self, cr, uid, order=False, context=None):
        """
        Compute the state of the field order.

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
        :param line: browse_record of the sale.order
        :param context: Context of the call

        :return The state of the sale order or False
        :rtype string
        """
        if context is None:
            context = {}

        self._check_browse_param(order, method='_get_sale_order_state')

        if order and order.state == 'done' and order.split_type_sale_order == 'original_sale_order':
            return 'split_so'
        elif order:
            return order.state

        return False

    def _get_date(self, cr, uid, line, context=None):
        """
        Compute the estimated delivery date of the line according
        to values already on line.

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
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
                                              context=context)
            res = get_delay.get('value', {}).get('estimated_delivery_date', False)

        return res

    def _get_line_values(self, cr, uid, ids, field_name, args, context=None):
        """
        Get some values from the field order line.

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
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
                'sale_order_state': self._get_sale_order_state(cr, uid, line, context=context),
            }
            res[line.id] = values

        return res

    # TODO: To refactore
    def _getAvailableStock(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """
        Get the available stock for each line

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
        :param ids: List of ID of field order lines to re-compute
        :param field_name: A field or a list of fields to be computed
        :param args: Some other arguments
        :param context: Context of the call

        :return A dictionnary with field order line id as keys and associated
                 available stock
        :rtype dict
        """
        result = {}
        productObj = self.pool.get('product.product')
        # for each sourcing line
        for sl in self.browse(cr, uid, ids, context):
            product_context = context
            if sl.product_id:
                real_stock = sl.real_stock
                product_context = context
                product_context.update({'states': ('assigned',), 'what': ('out',)})
                if sl.type == 'make_to_stock' and sl.location_id:
                    product_context.update({'location': sl.location_id.id})
                productId = productObj.get_product_available(cr, uid, [sl.product_id.id], context=product_context)
                res = real_stock + productId.get(sl.product_id.id, 0.00)
            else:
                res = 0.00

            result[sl.id] = res

        return result

    # TODO: To refactore
    def _getVirtualStock(self, cr, uid, ids, field_names=None, arg=False, context=None):
        '''
        get virtual stock (virtual_available) for the product of the corresponding sourcing line
        where date of stock.move is smaller than or equal to rts
        '''
        result = {}
        productObj = self.pool.get('product.product')

        # UF-1411 : Compute the virtual stock on Stock + Input locations
        location_ids = []
        wids = self.pool.get('stock.warehouse').search(cr, uid, [], context=context)
        for w in self.pool.get('stock.warehouse').browse(cr, uid, wids, context=context):
            location_ids.append(w.lot_stock_id.id)
            location_ids.append(w.lot_input_id.id)

        # for each sourcing line
        for sl in self.browse(cr, uid, ids, context):
            product_context = context
            rts = sl.rts < time.strftime('%Y-%m-%d') and time.strftime('%Y-%m-%d') or sl.rts
            if sl.type == 'make_to_stock' and sl.location_id:
                location_ids = sl.location_id.id
            product_context.update({'location': location_ids, 'to_date': '%s 23:59:59' % rts})
            if sl.product_id:
                product_virtual = productObj.browse(cr, uid, sl.product_id.id, context=product_context)
                res = {'real_stock': product_virtual.qty_available,
                       'virtual_stock': product_virtual.virtual_available}
            else:
                res = {'real_stock': 0.00,
                       'virtual_stock': 0.00}

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
        :param uid: ID of the user that launches the method
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
        if not args:
            return []

        if args[0][1] != '=' or not args[0][2]:
            raise osv.except_osv(_('Error !'), _('Filter not implemented'))

        return [('state', '=', 'draft'), ('sale_order_state', '=', 'validated')]

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
        # TODO: To refactore
        'display_confirm_button': fields.function(_get_line_values, method=True, type='boolean', string='Display Button', multi='line_info',),
        # TODO: To refactore
        'need_sourcing': fields.function(_get_fake, method=True, type='boolean', string='Only for filtering', fnct_search=_search_need_sourcing),
        # TODO: To refactore
        # UTP-392: if the FO is loan type, then the procurement method is only Make to Stock allowed
        'loan_type': fields.function(_get_line_values, method=True, type='boolean', multi='line_info',),
        # TODO: To refactore
        'sale_order_in_progress': fields.function(_get_line_values, method=True, type='boolean', multi='line_info'),
        # UTP-965 : Select a source stock location for line in make to stock
        # TODO: To refactore
        'real_stock': fields.function(_getVirtualStock, method=True, type='float', string='Real Stock', digits_compute=dp.get_precision('Product UoM'), readonly=True, multi='stock_qty'),
        # TODO: To refactore
        'virtual_stock': fields.function(_getVirtualStock, method=True, type='float', string='Virtual Stock', digits_compute=dp.get_precision('Product UoM'), readonly=True, multi='stock_qty'),
        # TODO: To refactore
        'available_stock': fields.function(_getAvailableStock, method=True, type='float', string='Available Stock', digits_compute=dp.get_precision('Product UoM'), readonly=True),
    }

    """
    Methods to check constraints
    """
    def _check_procurement_for_service_with_recep(self, cr, uid, ids, context=None):
        """
        If the product on line is a Service with Reception product, the procurement method
        should be 'Make to Order'.

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
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
    def default_get(self, cr, uid, fields, context=None):
        """
        Set default values (location_id) for sale_order_line

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
        :param fields: Fields to set
        :param context: Context of the call

        :return Dictionnary with fields as keys and default value
                 of field.
        :rtype dict
        """
        # Objects
        warehouse_obj = self.pool.get('stock.warehouse')

        res = super(sale_order_line, self).default_get(cr, uid, fields, context=context)

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
        :param uid: ID of the user that launches the method
        :param vals: A dictionary with values of the new line to create
        :param context: Context of the call

        :return The ID of the new line
        :rtype integer
        """
        # Objects
        order_obj = self.pool.get('sale.order')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if vals is None:
            vals = {}

        product = False
        if vals.get('product_id', False):
            product = product_obj.browse(cr, uid, vals['product_id'], context=context)

        if vals.get('order_id', False):
            order = order_obj.browse(cr, uid, vals['order_id'], context=context)
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

        # Create the new sale order line
        res = super(sale_order_line, self).create(cr, uid, vals, context=context)

        self._check_line_conditions(cr, uid, res, context)

        return res

    def _check_loan_conditions(self, cr, uid, line, context=None):
        """
        Check if the value of lines are compatible with the value
        of the order

        :param cr: Cursor to the database
        :param uid: ID of the user that launches the method
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
            return _('You can\'t source a loan \'from stock\'.')

        return False

    # TODO: TO REFACTORE
    def _check_line_conditions(self, cr, uid, ids, context=None):
        '''
        Check if the line have good values
        '''
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

            if line.type == 'make_to_order' and line.po_cft not in ['cft'] and not line.product_id and \
               line.order_id.procurement_request and line.supplier and line.supplier.partner_type not in ['internal', 'section', 'intermission']:
                raise osv.except_osv(_('Warning'), _("""For an Internal Request with a procurement method 'On Order' and without product, the supplier must be either in 'Internal', 'Inter-section' or 'Intermission type."""))

            if line.product_id and line.product_id.type in ('consu', 'service', 'service_recep') and line.type == 'make_to_stock':
                product_type = line.product_id.type == 'consu' and _('non stockable') or _('service')
                raise osv.except_osv(_('Warning'), _("""You cannot choose 'from stock' as method to source a %s product !""") % product_type)

            if line.product_id and line.po_cft == 'rfq' and line.supplier.partner_type in ['internal', 'section', 'intermission']:
                raise osv.except_osv(_('Warning'), _("""You can't source with 'Request for Quotation' to an internal/inter-section/intermission partner."""))

            if not line.product_id:
                if line.po_cft == 'cft':
                    raise osv.except_osv(_('Warning'), _("You can't source with 'Tender' if you don't have product."))
                if line.po_cft == 'rfq':
                    raise osv.except_osv(_('Warning'), _("You can't source with 'Request for Quotation' if you don't have product."))
                if line.type == 'make_to_stock':
                    raise osv.except_osv(_('Warning'), _("You can't Source 'from stock' if you don't have product."))
                if line.supplier and line.supplier.partner_type in ('external', 'esc'):
                    raise osv.except_osv(_('Warning'), _("You can't Source to an '%s' partner if you don't have product.") % (line.supplier.partner_type == 'external' and 'External' or 'ESC'))

            if line.state not in ('draft', 'cancel') and line.product_id and line.supplier:
                # Check product constraints (no external supply, no storage...)
                check_fnct = self.pool.get('product.product')._get_restriction_error
                self._check_product_constraints(cr, uid, line.type, line.po_cft, line.product_id.id, line.supplier.id, check_fnct, context=context)

            if line.order_id and line.order_id.procurement_request and line.type == 'make_to_stock':
                if line.order_id.location_requestor_id.id == line.location_id.id:
                    raise osv.except_osv(_('Warning'), _("You cannot choose a source location which is the destination location of the Internal Request"))

        return True

    # TODO: TO REFACTORE
    def _check_product_constraints(self, cr, uid, line_type='make_to_order', po_cft='po', product_id=False, partner_id=False, check_fnct=False, *args, **kwargs):
        '''
        Check product constraints (no extenal supply, no storage...)
        '''
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

    # TODO: TO REFACTORE
    def check_supplierinfo(self, cr, uid, ids, partner_id, context=None):
        '''
        return the value of delay if the corresponding supplier is in supplier info the product

        designed for one unique sourcing line as parameter (ids)
        '''
        for sourcing_line in self.browse(cr, uid, ids, context=context):
            delay = -1
            return sourcing_line.supplier and sourcing_line.supplier.supplier_lt or delay

    # TODO: TO REFACTORE
    def write(self, cr, uid, ids, vals, context=None):
        '''
        _inherit = 'sale.order.line'

        override to update sourcing_line :
         - supplier
         - type
         - po_cft
         - product_id
        '''
        result = True
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if vals.get('product_id', False):
            bropro = self.pool.get('product.product').browse(cr, uid, vals['product_id'])
            if bropro.type in ('consu', 'service', 'service_recep'):
                vals['type'] = 'make_to_order'

        if 'state' in vals and vals['state'] == 'cancel':
            self.write(cr, uid, ids, {'cf_estimated_delivery_date': False}, context=context)

        # partner_id
        for line in self.browse(cr, uid, ids, context=context):
            if 'supplier' in vals:
                partner_id = vals['supplier']
                vals.update({'supplier': partner_id})
                # update the delivery date according to partner_id, only update from the sourcing tool
                # not from order line as we dont want the date is udpated when the line's state changes for example
                if partner_id:
                    # if a new partner_id has been selected update the *sourcing_line* -> values
                    partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context)

                    # if the selected partner belongs to product->suppliers, we take that delay (from supplierinfo)
                    delay = self.check_supplierinfo(cr, uid, [line.id], partner_id, context=context)
                    # otherwise we take the default value from product form
                    if delay < 0:
                        delay = partner.default_delay

                    daysToAdd = delay
                    estDeliveryDate = date.today()
                    estDeliveryDate = estDeliveryDate + relativedelta(days=int(daysToAdd))
                    vals.update({'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d')})
                else:
                    # no partner is selected, erase the date
                    vals.update({'estimated_delivery_date': False})

        # update the corresponding sourcing line if not called from a sourcing line updated
        if 'fromSourcingLine' not in context:
            context['fromOrderLine'] = True
            values = {}
            if 'state' in vals:
                values.update({'state': vals['state']})
            if 'supplier' in vals:
                values.update({'supplier': vals['supplier']})
            if 'po_cft' in vals:
                values.update({'po_cft': vals['po_cft']})
            if 'type' in vals:
                values.update({'type': vals['type']})
                if vals['type'] == 'make_to_stock':
                    values.update({'po_cft': False})
                    vals.update({'po_cft': False})
                    values.update({'supplier': False})
                    vals.update({'supplier': False})
            if 'product_id' in vals:
                values.update({'product_id': vals['product_id']})
            if 'line_number' in vals:
                values.update({'line_number': vals['line_number']})
            if 'location_id' in vals:
                values.update({'location_id': vals['location_id']})

            # If lines are modified after the validation of the FO, update
            # lines values if the order is a loan

            # Search lines to modified with loan values
            loan_sol_ids = self.search(cr, uid, [('order_id.order_type', '=', 'loan'),
                                                 ('order_id.state', '=', 'validated'),
                                                 ('id', 'in', ids)], context=context)
            loan_sl_ids = self.search(cr, uid, [('id', 'in', loan_sol_ids)], context=context)

            # Other lines to modified with standard values
            sol_ids = self.search(cr, uid, [('id', 'in', ids), ('id', 'not in', loan_sol_ids)], context=context)
            sl_ids = self.search(cr, uid, [('id', 'in', sol_ids)], context=context)

            if loan_sol_ids:
                loan_vals = vals.copy()
                loan_values = values.copy()
                loan_data = {'type': 'make_to_stock',
                             'po_cft': False,
                             'suppier': False}
                loan_vals.update(loan_data)
                loan_values.update(loan_data)

                if loan_sl_ids:
                    # Update sourcing lines with loan
                    self.write(cr, uid, loan_sl_ids, loan_values, context)

                if loan_sol_ids:
                    # Update lines with loan
                    result = super(sale_order_line, self).write(cr, uid, loan_sol_ids, loan_vals, context)

            if sl_ids and values:
                # Update other sourcing lines
                self.write(cr, uid, sl_ids, values, context)
            if sol_ids and vals:
                # Update other lines
                result = super(sale_order_line, self).write(cr, uid, sol_ids, vals, context)
        else:
            # Just call the parent write()
            result = super(sale_order_line, self).write(cr, uid, ids, vals, context)

        return result

    # TODO: TO REFACTORE
    def confirmLine(self, cr, uid, ids, context=None):
        '''
        set the corresponding line's state to 'confirmed'
        if all lines are 'confirmed', the sale order is confirmed
        '''
        context = context or {}
        result = []
        for sl in self.browse(cr, uid, ids, context):
            # check if the line has a product for a Field Order (and not for an Internal Request)
            if not sl.product_id and not sl.sale_order_id.procurement_request:
                raise osv.except_osv(_('Warning'), _("""The product must be chosen before sourcing the line.
                Please select it within the lines of the associated Field Order (through the "Field Orders" menu).
                """))

            if sl.type == 'make_to_order' and sl.sale_order_id \
                    and sl.sale_order_id.state != 'draft' \
                    and sl.sale_order_id.order_type == 'loan':
                raise osv.except_osv(_('Warning'), _("""You can't source a loan 'from stock'."""))

            # corresponding state for the lines: IR: confirmed, FO: sourced
            state_to_use = sl.sale_order_id.procurement_request and 'confirmed' or 'sourced'
            # check if it is in On Order and if the Supply info is valid, if it's empty, just exit the action

            if sl.type == 'make_to_order' and not sl.po_cft in ['cft']:
                if not sl.supplier:
                    raise osv.except_osv(_('Warning'), _("The supplier must be chosen before sourcing the line"))
                # an Internal Request without product can only have Internal, Intersection or Intermission partners.
                elif sl.supplier and not sl.product_id and sl.sale_order_id.procurement_request and sl.supplier.partner_type not in ['internal', 'section', 'intermission']:
                    raise osv.except_osv(_('Warning'), _("""For an Internal Request with a procurement method 'On Order' and without product,
                    the supplier must be either in 'Internal', 'Inter-Section' or 'Intermission' type.
                    """))

            # set the corresponding sale order line to 'confirmed'
            result.append((sl.id, sl.sale_order_line_id.write({'state': state_to_use}, context)))
            # check if all order lines have been confirmed
            linesConfirmed = True
            for ol in sl.sale_order_id.order_line:
                if ol.state != state_to_use:
                    linesConfirmed = False
                    break
            # the line reads estimated_dd, after trg_validate, the lines are deleted, so all read/write must be performed before
            self.write(cr, uid, [sl.id], {'cf_estimated_delivery_date': sl.estimated_delivery_date}, context=context)
            # if all lines have been confirmed, we confirm the sale order
            if linesConfirmed:
                self.pool.get('sale.order').write(cr, uid, [sl.sale_order_id.id],
                                                    {'sourcing_trace_ok': True,
                                                     'sourcing_trace': 'Sourcing in progress'}, context=context)
                thread = threading.Thread(target=self.confirmOrder, args=(cr, uid, sl, context))
                thread.start()

        return result

    # TODO: TO REFACTORE
    def confirmOrder(self, cr, uid, sourcingLine, context=None, new_cursor=True):
        '''
        Confirm the Order in a Thread
        '''
        if not context:
            context = {}

        wf_service = netsvc.LocalService("workflow")

        if new_cursor:
            cr = pooler.get_db(cr.dbname).cursor()

        try:
            if sourcingLine.sale_order_id.procurement_request:
                wf_service.trg_validate(uid, 'sale.order', sourcingLine.sale_order_id.id, 'procurement_confirm', cr)
            else:
                wf_service.trg_validate(uid, 'sale.order', sourcingLine.sale_order_id.id, 'order_confirm', cr)
            self.pool.get('sale.order').write(cr, uid, [sourcingLine.sale_order_id.id],
                                              {'sourcing_trace_ok': False,
                                               'sourcing_trace': ''}, context=context)
        except osv.except_osv, e:
            cr.rollback()
            self.pool.get('sale.order').write(cr, uid, sourcingLine.sale_order_id.id,
                                              {'sourcing_trace_ok': True,
                                               'sourcing_trace': e.value}, context=context)
        except Exception, e:
            cr.rollback()
            self.pool.get('sale.order').write(cr, uid, sourcingLine.sale_order_id.id,
                                              {'sourcing_trace_ok': True,
                                               'sourcing_trace': misc.ustr(e)}, context=context)

        if new_cursor:
            cr.commit()
            cr.close()

        return True

    # TODO: TO REFACTORE
    def unconfirmLine(self, cr, uid, ids, context=None):
        '''
        set the sale order line state to 'draft'
        '''
        line_obj = self.pool.get('sale.order.line')
        result = []
        for sl in self.browse(cr, uid, ids, context):
            result.append((sl.id, line_obj.write(cr, uid, sl.sale_order_line_id.id, {'state':'draft'}, context)))

        return result


    """
    Controller methods
    """
    # TODO: TO REFACTORE
    def onChangeLocation(self, cr, uid, ids, location_id, product_id, rts, sale_order_id):
        '''
        Compute the stock values according to parameters
        '''
        prod_obj = self.pool.get('product.product')

        res = {'value': {}}

        if not location_id or not product_id:
            return res

        if sale_order_id:
            so = self.pool.get('sale.order').browse(cr, uid, sale_order_id)
            if so.procurement_request and so.location_requestor_id.id == location_id:
                return {'value': {'location_id': False,
                                  'real_stock': 0.00,
                                  'virtual_stock': 0.00,
                                  'available_stock': 0.00},
                        'warning': {'title': _('Warning'),
                                    'message': _('You cannot choose a source location which is the destination location of the Internal request')}}

        rts = rts < time.strftime('%Y-%m-%d') and time.strftime('%Y-%m-%d') or rts
        ctx = {'location': location_id, 'to_date': '%s 23:59:59' % rts}
        product = prod_obj.browse(cr, uid, product_id, context=ctx)
        res['value']['real_stock'] = product.qty_available
        res['value']['virtual_stock'] = product.virtual_available

        ctx2 = {'states': ('assigned',), 'what': ('out',), 'location': location_id}
        product2 = prod_obj.get_product_available(cr, uid, [product_id], context=ctx2)
        res['value']['available_stock'] = res['value']['real_stock'] + product2.get(product_id, 0.00)

        return res

    # TODO: TO REFACTORE
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
        uom=False, qty_uos=0, uos=False, name='', partner_id=False,
        lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        override to update hidden values :
         - supplier
         - type
         - po_cft
        '''
        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
                                                                uom, qty_uos, uos, name, partner_id,
                                                                lang, update_tax, date_order, packaging, fiscal_position, flag)

        # add supplier
        sellerId = False
        po_cft = False
        l_type = 'type' in result['value'] and result['value']['type']
        if product and type:
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            seller = productObj.seller_id
            sellerId = (seller and seller.id) or False

            if l_type == 'make_to_order':
                po_cft = 'po'

            result['value'].update({'supplier': sellerId, 'po_cft': po_cft})

        return result

    # TODO: TO REFACTORE
    def onChangePoCft(self, cr, uid, line_id, po_cft, order_id=False, partner_id=False, context=None):
        '''
        '''
        warning = {}
        value = {}

        if order_id:
            order = self.pool.get('sale.order').browse(cr, uid, order_id, context=context)
            if order.procurement_request and po_cft == 'dpo':
                warning = {'title': 'DPO for IR',
                           'message': 'You cannot choose Direct Purchase Order as method to source an Internal Request line.'}
                value = {'po_cft': 'po'}
            if po_cft == 'cft':
                # tender does not allow supplier selection
                value = {'supplier': False}


        if line_id and isinstance(line_id, list):
            line_id = line_id[0]

        res = {'value': value, 'warning': warning}

        line = self.browse(cr, uid, line_id, context=context)
        partner_id = 'supplier' in value and value['supplier'] or partner_id
        if line_id and partner_id and line.product_id:
            check_fnct = self.pool.get('product.product')._on_change_restriction_error
            res, error = self._check_product_constraints(cr, uid, line.type, value.get('po_cft', line.po_cft), line.product_id.id, partner_id, check_fnct, field_name='po_cft', values=res, vals={'partner_id': partner_id}, context=context)
            if error:
                return res

        return res
    # TODO: TO REFACTORE
    def onChangeType(self, cr, uid, line_id, l_type, location_id=False, context=None):
        '''
        if l_type == make to stock, change pocft to False
        '''
        if not context:
            context = {}

        value = {}
        message = {}
        if line_id:
            line = self.browse(cr, uid, line_id, context=context)[0]
            if line.product_id.type in ('consu', 'service', 'service_recep') and l_type == 'make_to_stock':
                product_type = line.product_id.type == 'consu' and 'non stockable' or 'service'
                value.update({'l_type': 'make_to_order'})
                message.update({'title': _('Warning'),
                                'message': _('You cannot choose \'from stock\' as method to source a %s product !') % product_type})

        if l_type == 'make_to_stock':
            if not location_id:
                wh_obj = self.pool.get('stock.warehouse')
                wh_ids = wh_obj.search(cr, uid, [], context=context)
                if wh_ids:
                    value.update({'location_id': wh_obj.browse(cr, uid, wh_ids[0], context=context).lot_stock_id.id})

            value.update({'po_cft': False})

            if line_id and isinstance(line_id, list):
                line_id = line_id[0]

            res = {'value': value, 'warning': message}
            if line_id:
                line = self.browse(cr, uid, line_id, context=context)
                check_fnct = self.pool.get('product.product')._on_change_restriction_error
                if line.product_id:
                    res, error = self._check_product_constraints(cr, uid, l_type, line.po_cft, line.product_id.id, False, check_fnct, field_name='l_type', values=res, vals={'constraints': ['storage']}, context=context)
                    if error:
                        return res

        return {'value': value, 'warning': message}
    # TODO: TO REFACTORE
    def onChangeSupplier(self, cr, uid, line_id, supplier, context=None):
        '''
        supplier changes, we update 'estimated_delivery_date' with corresponding delivery lead time
        we add a domain for the IR line on the supplier
        '''
        result = {'value':{}, 'domain':{}}

        if not supplier:
            for sl in self.browse(cr, uid, line_id, context):
                if not sl.product_id and sl.sale_order_id.procurement_request and sl.type == 'make_to_order':
                    result['domain'].update({'supplier': [('partner_type', 'in', ['internal', 'section', 'intermission'])]})
            return result

        partner = self.pool.get('res.partner').browse(cr, uid, supplier, context)
        # if the selected partner belongs to product->suppliers, we take that delay (from supplierinfo)
        delay = self.check_supplierinfo(cr, uid, line_id, partner.id, context=context)
        # otherwise we take the default value from product form
        if delay < 0:
            delay = partner.default_delay

        daysToAdd = delay
        estDeliveryDate = date.today()
        estDeliveryDate = estDeliveryDate + relativedelta(days=int(daysToAdd))

        result['value'].update({'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d')})

        if line_id and isinstance(line_id, list):
            line_id = line_id[0]

        line = self.browse(cr, uid, line_id, context=context)
        value = result['value']
        partner_id = 'supplier' in value and value['supplier'] or supplier
        if line_id and partner_id and line.product_id:
            check_fnct = self.pool.get('product.product')._on_change_restriction_error
            result, error = self._check_product_constraints(cr, uid, line.type, value.get('po_cft', line.po_cft), line.product_id.id, partner_id, check_fnct, field_name='supplier', values=result, vals={'partner_id': partner_id}, context=context)
            if error:
                return result

        return result

sale_order_line()

class procurement_order(osv.osv):
    """
    Procurement Orders

    modififed workflow to take into account
    the supplier specified during sourcing step
    """
    _inherit = "procurement.order"
    _description = "Procurement"
    _columns = {
        'supplier': fields.many2one('res.partner', 'Supplier'),
        'po_cft': fields.selection(_SELECTION_PO_CFT, string="PO/CFT"),
    }

    def po_line_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order

        - allow to modify the data for purchase order line creation
        '''
        if not context:
            context = {}
        line = super(procurement_order, self).po_line_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        origin_line = False
        if 'procurement' in kwargs:
            order_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', kwargs['procurement'].id)])
            if order_line_ids:
                origin_line = self.pool.get('sale.order.line').browse(cr, uid, order_line_ids[0])
                line.update({'origin': origin_line.order_id.name, 'product_uom': origin_line.product_uom.id, 'product_qty': origin_line.product_uom_qty})
            else:
                # Update the link to the original FO to create new line on it at PO confirmation
                procurement = kwargs['procurement']
                if procurement.origin:
                    link_so = self.pool.get('purchase.order.line').update_origin_link(cr, uid, procurement.origin, context=context)
                    if link_so.get('link_so_id'):
                        line.update({'origin': procurement.origin, 'link_so_id': link_so.get('link_so_id')})

            # UTP-934: If the procurement is a rfq, the price unit must be taken from this rfq, and not from the pricelist or standard price
            procurement = kwargs['procurement']
            if procurement.po_cft in ('cft', 'rfq') and procurement.price_unit:
                line.update({'price_unit': procurement.price_unit})

        if line.get('price_unit', False) == False:
            cur_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
            if 'pricelist' in kwargs:
                if 'procurement' in kwargs and 'partner_id' in context:
                    procurement = kwargs['procurement']
                    pricelist = kwargs['pricelist']
                    st_price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist.id], procurement.product_id.id, procurement.product_qty, context['partner_id'], {'uom': line.get('product_uom', procurement.product_id.uom_id.id)})[pricelist.id]
                st_price = self.pool.get('res.currency').compute(cr, uid, cur_id, kwargs['pricelist'].currency_id.id, st_price, round=False, context=context)
            if not st_price:
                product = self.pool.get('product.product').browse(cr, uid, line['product_id'])
                st_price = product.standard_price
                if 'pricelist' in kwargs:
                    st_price = self.pool.get('res.currency').compute(cr, uid, cur_id, kwargs['pricelist'].currency_id.id, st_price, round=False, context=context)
                elif 'partner_id' in context:
                    partner = self.pool.get('res.partner').browse(cr, uid, context['partner_id'], context=context)
                    st_price = self.pool.get('res.currency').compute(cr, uid, cur_id, partner.property_product_pricelist_purchase.currency_id.id, st_price, round=False, context=context)
                if origin_line:
                    st_price = self.pool.get('product.uom')._compute_price(cr, uid, product.uom_id.id, st_price or product.standard_price, to_uom_id=origin_line.product_uom.id)
            line.update({'price_unit': st_price})

        return line

    def action_check_finished(self, cr, uid, ids):
        res = super(procurement_order, self).action_check_finished(cr, uid, ids)

        # If the procurement has been generated from an internal request, close the order
        for order in self.browse(cr, uid, ids):
            line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', order.id)])
            for line in self.pool.get('sale.order.line').browse(cr, uid, line_ids):
                if line.order_id.procurement_request and line.order_id.location_requestor_id.usage != 'customer':
                    return True

        return res

    def create_po_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        if a purchase order for the same supplier and the same requested date,
        don't create a new one
        '''
        po_obj = self.pool.get('purchase.order')
        procurement = kwargs['procurement']
        values = kwargs['values']
        priority_sorted = {'emergency': 1, 'priority': 2, 'normal': 3}
        # Make the line as price changed manually to do not raise an error on purchase order line creation
#        if 'order_line' in values and len(values['order_line']) > 0 and len(values['order_line'][0]) > 2 and 'price_unit' in values['order_line'][0][2]:
#            values['order_line'][0][2].update({'change_price_manually': True})

        partner = self.pool.get('res.partner').browse(cr, uid, values['partner_id'], context=context)

        purchase_domain = [('partner_id', '=', partner.id),
                           ('state', '=', 'draft'),
                           ('rfq_ok', '=', False),
                           ('delivery_requested_date', '=', values.get('delivery_requested_date'))]

        if procurement.po_cft == 'dpo':
            purchase_domain.append(('order_type', '=', 'direct'))
        else:
            purchase_domain.append(('order_type', '!=', 'direct'))

        line = None
        sale_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        if sale_line_ids:
            line = self.pool.get('sale.order.line').browse(cr, uid, sale_line_ids[0], context=context)

        if partner.po_by_project in ('project', 'category_project') or (procurement.po_cft == 'dpo' and partner.po_by_project == 'all'):
            if line:
                if line.procurement_request:
                    customer_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
                else:
                    customer_id = line.order_id.partner_id.id
                values.update({'customer_id': customer_id})
                purchase_domain.append(('customer_id', '=', customer_id))

        # Isolated requirements => One PO for one IR/FO
        if partner.po_by_project == 'isolated':
            purchase_domain.append(('origin', '=', procurement.origin))

        # Category requirements => Search a PO with the same category than the IR/FO category
        if partner.po_by_project in ('category_project', 'category'):
            if line:
                purchase_domain.append(('categ', '=', line.order_id.categ))

        # if we are updating the sale order from the corresponding on order purchase order
        # the purchase order to merge the new line to is locked and provided in the procurement
        if procurement.so_back_update_dest_po_id_procurement_order:
            purchase_ids = [procurement.so_back_update_dest_po_id_procurement_order.id]
        else:
            # search for purchase order according to defined domain
            purchase_ids = po_obj.search(cr, uid, purchase_domain, context=context)

        # Set the origin of the line with the origin of the Procurement order
        if procurement.origin:
            values['order_line'][0][2].update({'origin': procurement.origin})

        if procurement.tender_id:
            if values.get('origin'):
                values['origin'] = '%s; %s' % (values['origin'], procurement.tender_id.name)
            else:
                values['origin'] = procurement.tender_id.name

        if procurement.rfq_id:
            if values.get('origin'):
                values['origin'] = '%s; %s' % (values['origin'], procurement.rfq_id.name)
            else:
                values['origin'] = procurement.rfq_id.name

        # Set the analytic distribution on PO line if an analytic distribution is on SO line or SO
        sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        location_id = False
        categ = False
        if sol_ids:
            sol = self.pool.get('sale.order.line').browse(cr, uid, sol_ids[0], context=context)
            if sol.order_id:
                categ = sol.order_id.categ

            if sol.analytic_distribution_id:
                new_analytic_distribution_id = self.pool.get('analytic.distribution').copy(cr, uid,
                                                    sol.analytic_distribution_id.id, context=context)
                values['order_line'][0][2].update({'analytic_distribution_id': new_analytic_distribution_id})
            elif sol.order_id.analytic_distribution_id:
                new_analytic_distribution_id = self.pool.get('analytic.distribution').copy(cr,
                                                    uid, sol.order_id.analytic_distribution_id.id, context=context)
                values['order_line'][0][2].update({'analytic_distribution_id': new_analytic_distribution_id})
        elif procurement.product_id:
            if procurement.product_id.type == 'consu':
                location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
            elif procurement.product_id.type == 'service_recep':
                location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_service')[1]
            else:
                wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
                if wh_ids:
                    location_id = self.pool.get('stock.warehouse').browse(cr, uid, wh_ids[0]).lot_input_id.id
                else:
                    location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_service')[1]

        if purchase_ids:
            line_values = values['order_line'][0][2]
            line_values.update({'order_id': purchase_ids[0], 'origin': procurement.origin})
            po = self.pool.get('purchase.order').browse(cr, uid, purchase_ids[0], context=context)
            # Update the origin of the PO with the origin of the procurement
            # and tender name if exist
            origins = set([po.origin, procurement.origin, procurement.tender_id and procurement.tender_id.name, procurement.rfq_id and procurement.rfq_id.name])
            # Add different origin on 'Source document' field if the origin is nat already listed
            origin = ';'.join(o for o in list(origins) if o and (not po.origin or o == po.origin or o not in po.origin))
            write_values = {'origin': origin}

            # update categ and prio if they are different from the existing po one's.
            if values.get('categ') and values['categ'] != po.categ:
                write_values['categ'] = 'other'
            if values.get('priority') and values['priority'] in priority_sorted.keys() and values['priority'] != po.priority:
                if priority_sorted[values['priority']] < priority_sorted[po.priority]:
                    write_values['priority'] = values['priority']

            self.pool.get('purchase.order').write(cr, uid, purchase_ids[0], write_values, context=dict(context, import_in_progress=True))

            po_values = {}
            if categ and po.categ != categ:
                po_values.update({'categ': 'other'})

            if location_id:
                po_values.update({'location_id': location_id, 'cross_docking_ok': False})

            if po_values:
                self.pool.get('purchase.order').write(cr, uid, purchase_ids[0], po_values, context=dict(context, import_in_progress=True))
            self.pool.get('purchase.order.line').create(cr, uid, line_values, context=context)
            return purchase_ids[0]
        else:
            if procurement.po_cft == 'dpo':
                sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
                if sol_ids:
                    sol = self.pool.get('sale.order.line').browse(cr, uid, sol_ids[0], context=context)
                    if not sol.procurement_request:
                        values.update({'order_type': 'direct',
                                       'dest_partner_id': sol.order_id.partner_id.id,
                                       'dest_address_id': sol.order_id.partner_shipping_id.id})

                #  Force the destination location of the Po to Input location
                company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
                warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [('company_id', '=', company_id)], context=context)
                if warehouse_id:
                    input_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id[0], context=context).lot_input_id.id
                    values.update({'location_id': input_id, })
            if categ:
                values.update({'categ': categ})
            purchase_id = super(procurement_order, self).create_po_hook(cr, uid, ids, context=context, *args, **kwargs)
            return purchase_id

    def write(self, cr, uid, ids, vals, context=None):
        '''
        override for workflow modification
        '''
        return super(procurement_order, self).write(cr, uid, ids, vals, context)

    def _partner_check_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        check the if supplier is available or not

        the new selection field does not exist when the procurement has been produced by
        an order_point (minimum stock rules). in this case we take the default supplier from product

        same cas if no supplier were selected in the sourcing tool

        return True if a supplier is available
        '''
        procurement = kwargs['procurement']
        # add supplier check in procurement object from sourcing tool
        result = procurement.supplier or super(procurement_order, self)._partner_check_hook(cr, uid, ids, context=context, *args, **kwargs)
        return result

    def _partner_get_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        returns the partner from procurement or suppinfo

        the new selection field does not exist when the procurement has been produced by
        an order_point (minimum stock rules). in this case we take the default supplier from product

        same cas if no supplier were selected in the sourcing tool
        '''
        procurement = kwargs['procurement']
        # the specified supplier in sourcing tool has priority over suppinfo
        partner = procurement.supplier or super(procurement_order, self)._partner_get_hook(cr, uid, ids, context=context, *args, **kwargs)
        if partner.id == self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id:
            cr.execute('update procurement_order set message=%s where id=%s',
                           (_('Impossible to make a Purchase Order to your own company !'), procurement.id))
        return partner

    def get_delay_qty(self, cr, uid, ids, partner, product, context=None):
        '''
        find corresponding values for seller_qty and seller_delay from product supplierinfo or default values
        '''
        result = {}
        # if the supplier is present in product seller_ids, we take that quantity from supplierinfo
        # otherwise 1
        # seller_qty default value
        seller_qty = 1
        seller_delay = -1
        for suppinfo in product.seller_ids:
            if suppinfo.name.id == partner.id:
                seller_qty = suppinfo.qty
                seller_delay = int(suppinfo.delay)

        # if not, default delay from supplier (partner.default_delay)
        if seller_delay < 0:
            seller_delay = partner.default_delay

        result.update(seller_qty=seller_qty,
                      seller_delay=seller_delay,)

        return result

    def get_partner_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        get data from supplier

        return also the price_unit
        '''
        # get default values
        result = super(procurement_order, self).get_partner_hook(cr, uid, ids, context=context, *args, **kwargs)
        procurement = kwargs['procurement']

        # this is kept here and not moved in the tender_flow module
        # because we have no control on the order of inherited function call (do we?)
        # and if we have tender and supplier defined and supplier code is ran after
        # tender one, the supplier will be use while tender has priority
        if procurement.is_tender:
            # tender line -> search for info about this product in the corresponding tender
            # if nothing found, we keep default values from super
            for sol in procurement.sale_order_line_ids:
                for tender_line in sol.tender_line_ids:
                    # if a tender rfq has been selected for this sale order line
                    if tender_line.purchase_order_line_id:
                        partner = tender_line.supplier_id
                        price_unit = tender_line.price_unit
                        # get corresponding delay and qty
                        delay_qty = self.get_delay_qty(cr, uid, ids, partner, procurement.product_id, context=None)
                        seller_delay = delay_qty['seller_delay']
                        seller_qty = delay_qty['seller_qty']
                        result.update(partner=partner,
                                      seller_qty=seller_qty,
                                      seller_delay=seller_delay,
                                      price_unit=price_unit)
        elif procurement.supplier:
            # not tender, we might have a selected supplier from sourcing tool
            # if not, we keep default values from super
            partner = procurement.supplier
            # get corresponding delay and qty
            delay_qty = self.get_delay_qty(cr, uid, ids, partner, procurement.product_id, context=None)
            seller_delay = delay_qty['seller_delay']
            seller_qty = delay_qty['seller_qty']
            result.update(partner=partner,
                          seller_qty=seller_qty,
                          seller_delay=seller_delay)

        return result

procurement_order()

class purchase_order(osv.osv):
    '''
    override for workflow modification
    '''
    _inherit = "purchase.order"
    _description = "Purchase Order"

    _columns = {
        'customer_id': fields.many2one('res.partner', string='Customer', domain=[('customer', '=', True)]),
    }

    def create(self, cr, uid, vals, context=None):
        '''
        override for debugging purpose
        '''
        return super(purchase_order, self).create(cr, uid, vals, context)

    def _check_order_type_and_partner(self, cr, uid, ids, context=None):
        """
        Check order type and partner type compatibilities.
        """
        compats = {
            'regular':       ['internal', 'intermission', 'section', 'external', 'esc'],
            'donation_st':   ['internal', 'intermission', 'section'],
            'loan':          ['internal', 'intermission', 'section', 'external'],
            'donation_exp':  ['internal', 'intermission', 'section'],
            'in_kind':       ['external', 'esc'],
            'direct':        ['external', 'esc'],
            'purchase_list': ['external'],
        }
        # Browse PO
        for po in self.browse(cr, uid, ids):
            if po.order_type not in compats or po.partner_id.partner_type not in compats[po.order_type]:
                return False
        return True

    _constraints = [
        (_check_order_type_and_partner, "Partner type and order type are incompatible! Please change either order type or partner.", ['order_type', 'partner_id']),
    ]

purchase_order()

class product_template(osv.osv):
    '''
    override to add new seller_info_id : default seller but supplierinfo object
    '''
    def _calc_seller(self, cr, uid, ids, fields, arg, context=None):
        result = super(product_template, self)._calc_seller(cr, uid, ids, fields, arg, context)

        for product in self.browse(cr, uid, ids, context=context):
            if product.seller_ids:
                partner_list = sorted([(partner_id.sequence, partner_id) for partner_id in  product.seller_ids if partner_id and partner_id.sequence])
                main_supplier = partner_list and partner_list[0] and partner_list[0][1] or False
                result[product.id]['seller_info_id'] = main_supplier and main_supplier.id or False
        return result

    _inherit = "product.template"
    _description = "Product Template"
    _columns = {
                'seller_info_id': fields.function(_calc_seller, method=True, type='many2one', relation='product.supplierinfo', string='Main Supplier Info', help="Main Supplier who has highest priority in Supplier List - Info object.", multi="seller_id"),
                }

product_template()

class product_supplierinfo(osv.osv):
    '''
    override name_get to display name of the related supplier

    override create to be able to create a new supplierinfo from sourcing view
    '''
    _inherit = "product.supplierinfo"
    _description = "Information about a product supplier"

    def _get_false(self, cr, uid, ids, field_name, arg, context=None):
        '''
        return false for each id
        '''
        if isinstance(ids, (long, int)):
            ids = [ids]

        result = {}
        for l_id in ids:
            result[l_id] = []
        return result

    def _get_product_ids(self, cr, uid, obj, name, args, context=None):
        '''
        from the product.template id returns the corresponding product.product
        '''
        if not args:
            return []
        if args[0][1] != '=':
            raise osv.except_osv(_('Error !'), _('Filter not implemented'))
        # product id of sourcing line
        productId = args[0][2]
        # gather product template id for that product
        templateId = self.pool.get('product.product').browse(cr, uid, productId, context=context).product_tmpl_id.id
        # search filter on product_id of supplierinfo
        return [('product_id', '=', templateId)]

    _columns = {'product_product_ids': fields.function(_get_false, method=True, type='one2many', relation='product.product', string="Products", fnct_search=_get_product_ids),
                }

    def name_get(self, cr, uid, ids, context=None):
        '''
        product_supplierinfo
        display the name of the product instead of the id of supplierinfo
        '''
        if not ids:
            return []

        result = []
        for supinfo in self.browse(cr, uid, ids, context=context):
            supplier = supinfo.name
            result.append((supinfo.id, supplier.name_get(context=context)[0][1]))

        return result

    def create(self, cr, uid, values, context=None):
        '''
        product_supplierinfo
        inject product_id in newly created supplierinfo
        '''
        if not values:
            values = {}
        if context and 'sourcing-product_id' in context:
            productId = context['sourcing-product_id']
            product = self.pool.get('product.product').browse(cr, uid, productId, context=context)
            values.update({'product_id': product.product_tmpl_id.id})

        return super(product_supplierinfo, self).create(cr, uid, values, context)

product_supplierinfo()


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def _get_available_for_dpo(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return for each partner if he's available for DPO selection
        '''
        res = {}
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id

        for partner in self.browse(cr, uid, ids, context=context):
            res[partner.id] = False
            if partner.supplier and partner.id != company_id and partner.partner_type in ('external', 'esc'):
                res[partner.id] = True

        return res

    def _src_available_for_dpo(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all partners according to args
        '''
        res = []
        for arg in args:
            if len(arg) > 2 and arg[0] == 'available_for_dpo':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error'), _('Bad operator'))
                elif arg[2] == 'dpo':
                    company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
                    res.append(('id', '!=', company_id))
                    res.append(('partner_type', 'in', ('external', 'esc')))
                    res.append(('supplier', '=', True))

        return res

    def _get_fake(self, cr, uid, ids, fields, arg, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        result = {}
        for l_id in ids:
            result[l_id] = False
        return result

    def _check_partner_type(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        active_id = context.get('active_id', False)
        if isinstance(active_id, (int, long)):
            active_id = [active_id]
        if not args:
            return []
        newargs = []
        for arg in args:
            if arg[0] == 'check_partner':
                if arg[1] != '=' or not isinstance(arg[2], (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter check_partner different than (arg[0], =, id) not implemented.'))
                if arg[2]:
                    so = self.pool.get('sale.order').browse(cr, uid, arg[2])
                    sl = self.browse(cr, uid, active_id)[0]
                    if not so.procurement_request:
                        newargs.append(('partner_type', 'in', ['external', 'esc']))
                    elif so.procurement_request and not sl.product_id:
                        newargs.append(('partner_type', 'in', ['internal', 'section', 'intermission']))
            else:
                newargs.append(args)
        return newargs

    def _check_partner_type_rfq(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        newargs = []
        for arg in args:
            if arg[0] == 'check_partner_rfq':
                if arg[1] != '=' or not isinstance(arg[2], (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter check_partner_rfq different than (arg[0], =, id) not implemented.'))
                if arg[2]:
                    tender = self.pool.get('tender').browse(cr, uid, arg[2])
                    if tender.sale_order_id:
                        newargs.append(('partner_type', 'in', ['external', 'esc']))
            else:
                newargs.append(args)
        return newargs

    def _check_partner_type_ir(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        active_ids = context.get('active_ids', False)
        if isinstance(active_ids, (int, long)):
            active_ids = [active_ids]
        if not args:
            return []
        newargs = []
        for arg in args:
            if arg[0] == 'check_partner_ir':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error'), _('Filter check_partner_ir different than (arg[0], =, id) not implemented.'))
                if arg[2]:
                    if active_ids:
                        sol = self.pool.get('sale.order.line').browse(cr, uid, active_ids)[0]
                        if not context.get('product_id', False) and sol.order_id.procurement_request:
                            newargs.append(('partner_type', 'in', ['internal', 'section', 'intermission']))
            else:
                newargs.append(args)
        return newargs

    def _check_partner_type_po(self, cr, uid, obj, name, args, context=None):
        """
        Create a domain on the field partner_id on the view id="purchase_move_buttons"
        """
        if context is None:
            context = {}
        if not args:
            return []
        newargs = []

        for arg in args:
            if arg[0] == 'check_partner_po':
                if arg[1] != '=' \
                or arg[2]['order_type'] not in ['regular', 'donation_exp', 'donation_st', 'loan', 'in_kind', 'purchase_list', 'direct']\
                or not isinstance(arg[2]['partner_id'], (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter check_partner_po different than (arg[0], =, %s) not implemented.') % arg[2])
                order_type = arg[2]['order_type']
                # Added by UF-1660 to filter partners
                # do nothing on partner_type for loan
                p_list = []
                if order_type == 'loan':
                    p_list = ['internal', 'intermission', 'section', 'external']
                elif order_type in ['direct', 'in_kind']:
                    p_list = ['esc', 'external']
                elif order_type in ['donation_st', 'donation_exp']:
                    p_list = ['internal', 'intermission', 'section']
                elif order_type in ['purchase_list']:
                    p_list = ['external']
                # show all supplier for non taken cases
                else:
                    pass
                if p_list:
                    newargs.append(('partner_type', 'in', p_list))
            else:
                newargs.append(args)
        return newargs

    _columns = {
        'available_for_dpo': fields.function(_get_available_for_dpo, fnct_search=_src_available_for_dpo,
                                             method=True, type='boolean', string='Available for DPO', store=False),
        'check_partner': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type', fnct_search=_check_partner_type),
        'check_partner_rfq': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type', fnct_search=_check_partner_type_rfq),
        'check_partner_ir': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type On IR', fnct_search=_check_partner_type_ir),
        'check_partner_po': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type On PO', fnct_search=_check_partner_type_po),
    }

res_partner()
