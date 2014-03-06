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

_SELECTION_PO_CFT = [
                     ('po', 'Purchase Order'),
                     ('dpo', 'Direct Purchase Order'),
                     ('cft', 'Tender'),
                     ('rfq', 'Request for Quotation'),
                     ]

class sourcing_line(osv.osv):
    '''
    Class for sourcing_line

    Sourcing lines are generated when a Sale Order is created
    (overriding of create method of sale_order)
    '''

    def get_sale_order_states(self, cr, uid, context=None):
        '''
        Returns all states values for a sale.order object
        '''
        return self.pool.get('sale.order')._columns['state'].selection

    def get_sale_order_line_states(self, cr, uid, context=None):
        '''
        Returns all states values for a sale.order.line object
        '''
        return self.pool.get('sale.order.line')._columns['state'].selection


    _SELECTION_TYPE = [
                       ('make_to_stock', 'from stock'),
                       ('make_to_order', 'on order'),
                       ]

    _SELECTION_SALE_ORDER_STATE = get_sale_order_states

    _SELECTION_SALE_ORDER_LINE_STATE = get_sale_order_line_states

    def unlink(self, cr, uid, ids, context=None):
        '''
        if unlink does not result of a call from sale_order_line, raise an exception
        '''
        if not context:
            context = {}
        if ('fromSaleOrderLine' not in context) and ('fromSaleOrder' not in context):
            raise osv.except_osv(_('Invalid action !'), _('Cannot delete Sale Order Line(s) from the sourcing tool !'))
        # delete the sourcing line
        return super(sourcing_line, self).unlink(cr, uid, ids, context)

    def _getAvailableStock(self, cr, uid, ids, field_names=None, arg=False, context=None):
        '''
        get available stock for the product of the corresponding sourcing line
        '''
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

    _name = 'sourcing.line'
    _description = 'Sourcing Line'

    def _get_sourcing_vals(self, cr, uid, ids, fields, arg, context=None):
        '''
        returns the value from the sale.order
        '''
        if isinstance(fields, str):
            fields = [fields]
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f: False, })
            # gather procurement_request boolean
            result[obj.id]['procurement_request'] = obj.sale_order_id and obj.sale_order_id.procurement_request or False
            # gather sale order line state
            result[obj.id]['state'] = obj.sale_order_line_id and obj.sale_order_line_id.state or False
            # display confirm button - display if state == draft and not proc or state == progress and proc
            result[obj.id]['display_confirm_button'] = (obj.state == 'draft' and obj.sale_order_id.state == 'validated')
            # UTP-392: readonly for procurement method if it is a Loan type
            result[obj.id]['loan_type'] = (obj.sale_order_id.order_type == 'loan')
            # Sourcing in progress
            result[obj.id]['sale_order_in_progress'] = obj.sale_order_id.sourcing_trace_ok
            # sale_order_state
            result[obj.id]['sale_order_state'] = False
            if obj.sale_order_id:
                result[obj.id]['sale_order_state'] = obj.sale_order_id.state
                if obj.sale_order_id.state == 'done' and obj.sale_order_id.split_type_sale_order == 'original_sale_order':
                    result[obj.id]['sale_order_state'] = 'split_so'

        return result

    def _get_sale_order_ids(self, cr, uid, ids, context=None):
        '''
        self represents sale.order
        ids represents the ids of sale.order objects for which procurement_request has changed

        return the list of ids of sourcing.line object which need to get their procurement_request field updated
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # list of sourcing lines having sale_order_id within ids
        result = self.pool.get('sourcing.line').search(cr, uid, [('sale_order_id', 'in', ids)], context=context)
        return result


    def _get_sale_order_line_ids(self, cr, uid, ids, context=None):
        '''
        self represents sale.order.line
        ids represents the ids of sale.order.line objects for which state / procurement_request has changed

        return the list of ids of sourcing.line object which need to get their state / procurement_request fields updated
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # list of sourcing lines having sale_order_line_id within ids
        return self.pool.get('sourcing.line').search(cr, uid, [('sale_order_line_id', 'in', ids)], context=context)

    def _get_souring_lines_ids(self, cr, uid, ids, context=None):
        '''
        self represents sourcing.line
        ids represents the ids of sourcing.line objects for which a field has changed

        return the list of ids of sourcing.line object which need to get their field updated
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        result = ids
        return result

    def _get_fake(self, cr, uid, ids, fields, arg, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        result = {}
        for line_id in ids:
            result[line_id] = False
        return result

    def _search_need_sourcing(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []

        if args[0][1] != '=' or not args[0][2]:
            raise osv.except_osv(_('Error !'), _('Filter not implemented'))

        return [('state', '=', 'draft'), ('sale_order_state', '=', 'validated')]

    def _search_sale_order_state(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        newargs = []

        for arg in args:
            if arg[1] != '=':
                raise osv.except_osv(_('Error !'), _('Filter not implemented'))

            if arg[2] == 'progress':
                newargs.append(('sale_order_state', 'in', ['progress', 'manual']))
            else:
                newargs.append(('sale_order_state', arg[1], arg[2]))
        return newargs

    def _get_date(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'estimated_delivery_date': False,
                            'rts': False}
            if line.supplier:
                delay = self.onChangeSupplier(cr, uid, [line.id], line.supplier.id, context=context).get('value', {}).get('estimated_delivery_date', False)
                res[line.id]['estimated_delivery_date'] = line.cf_estimated_delivery_date and line.state in ('done', 'confirmed') and line.cf_estimated_delivery_date or delay

# #            tr_lt = line.sale_order_id and line.sale_order_id.est_transport_lead_time or 0.00
#            ship_lt = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.shipment_lead_time
#            res[line.id]['rts'] = datetime.strptime(line.sale_order_line_id.date_planned, '%Y-%m-%d') - relativedelta(days=int(tr_lt)) - relativedelta(days=int(ship_lt))
#            res[line.id]['rts'] = res[line.id]['rts'].strftime('%Y-%m-%d')
            res[line.id]['rts'] = line.sale_order_id.ready_to_ship_date

        return res

    _columns = {
        # sequence number
        'name': fields.char('Name', size=128),
        'sale_order_id': fields.many2one('sale.order', 'Order', on_delete='cascade', readonly=True),
        'sale_order_line_id': fields.many2one('sale.order.line', 'Order Line', on_delete='cascade', readonly=True),
        'customer': fields.many2one('res.partner', 'Customer', readonly=True),
        'reference': fields.related('sale_order_id', 'name', type='char', size=128, string='Reference', readonly=True),
#        'state': fields.related('sale_order_line_id', 'state', type="selection", selection=_SELECTION_SALE_ORDER_LINE_STATE, readonly=True, string="State", store=False),
        'state': fields.function(_get_sourcing_vals, method=True, type='selection', selection=_SELECTION_SALE_ORDER_LINE_STATE, string='State', multi='get_vals_sourcing',
                                  store={'sale.order.line': (_get_sale_order_line_ids, ['state'], 10),
                                         'sourcing.line': (_get_souring_lines_ids, ['sale_order_line_id'], 10)}),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True),
        'categ': fields.selection(ORDER_CATEGORY, string='Category', readonly=True),
        # I do not directly set the store on state_hidden_sale_order because I did not find definitive clue that dynamic store could be used in cascade
        'sale_order_state': fields.function(_get_sourcing_vals, method=True, readonly=True, type='selection', selection=_SELECTION_SALE_ORDER_STATE, string='Order State', multi='get_vals_sourcing',
                                            store={'sale.order': (_get_sale_order_ids, ['state', 'split_type_sale_order'], 10),
                                                   'sourcing.line': (_get_souring_lines_ids, ['sale_order_id'], 10)}),
#        'sale_order_state': fields.selection(_SELECTION_SALE_ORDER_STATE, string="Order State", readonly=True),
        'sale_order_state_search': fields.function(_get_fake, string="Order State", type='selection', method=True, selection=[x for x in SALE_ORDER_STATE_SELECTION if x[0] != 'manual'], fnct_search=_search_sale_order_state),
        'line_number': fields.integer(string='Line', readonly=True),
        'product_id': fields.many2one('product.product', string='Product', readonly=True),
        'qty': fields.related('sale_order_line_id', 'product_uom_qty', type='float', string='Quantity', readonly=True),
        'uom_id': fields.related('sale_order_line_id', 'product_uom', relation='product.uom', type='many2one', string='UoM', readonly=True),
        # 'rts': fields.related('sale_order_id', 'ready_to_ship_date', type='date', string='RTS', readonly=True),
        'rts': fields.function(_get_date, type='date', method=True, string='RTS', readonly=True, store=False, multi='dates'),
        'sale_order_line_state': fields.related('sale_order_line_id', 'state', type="selection", selection=_SELECTION_SALE_ORDER_LINE_STATE, readonly=True, store=False),
        'type': fields.selection(_SELECTION_TYPE, string='Procurement Method', readonly=True, states={'draft': [('readonly', False)]}),
        'po_cft': fields.selection(_SELECTION_PO_CFT, string='PO/CFT', readonly=True, states={'draft': [('readonly', False)]}),
        # 'real_stock': fields.related('product_id', 'qty_available', type='float', string='Real Stock', readonly=True),
        'real_stock': fields.function(_getVirtualStock, method=True, type='float', string='Real Stock', digits_compute=dp.get_precision('Product UoM'), readonly=True, multi='stock_qty'),
        'virtual_stock': fields.function(_getVirtualStock, method=True, type='float', string='Virtual Stock', digits_compute=dp.get_precision('Product UoM'), readonly=True, multi='stock_qty'),
        'available_stock': fields.function(_getAvailableStock, method=True, type='float', string='Available Stock', digits_compute=dp.get_precision('Product UoM'), readonly=True),
        'stock_uom_id': fields.related('product_id', 'uom_id', string='UoM', type='many2one', relation='product.uom'),
        'supplier': fields.many2one('res.partner', 'Supplier', readonly=True, states={'draft': [('readonly', False)]}, domain=[('supplier', '=', True)]),
        'cf_estimated_delivery_date': fields.date(string='Estimated DD', readonly=True),
        'estimated_delivery_date': fields.function(_get_date, type='date', method=True, store=False, string='Estimated DD', readonly=True, multi='dates'),
        'company_id': fields.many2one('res.company', 'Company', select=1),
        'procurement_request': fields.function(_get_sourcing_vals, method=True, type='boolean', string='Procurement Request', multi='get_vals_sourcing',
                                               store={'sale.order': (_get_sale_order_ids, ['procurement_request'], 10),
                                                      'sale.order.line': (_get_sale_order_line_ids, ['procurement_request'], 10),
                                                      'sourcing.line': (_get_souring_lines_ids, ['sale_order_id'], 10)}),
        'display_confirm_button': fields.function(_get_sourcing_vals, method=True, type='boolean', string='Display Button', multi='get_vals_sourcing',),
        'need_sourcing': fields.function(_get_fake, method=True, type='boolean', string='Only for filtering', fnct_search=_search_need_sourcing),

        # UTP-392: if the FO is loan type, then the procurement method is only Make to Stock allowed
        'loan_type': fields.function(_get_sourcing_vals, method=True, type='boolean', multi='get_vals_sourcing',),
        'sale_order_in_progress': fields.function(_get_sourcing_vals, method=True, type='boolean', multi='get_vals_sourcing'),
        # UTP-965 : Select a source stock location for line in make to stock
        'location_id': fields.many2one('stock.location', string='Location'),
    }
    _order = 'sale_order_id desc, line_number'
    _defaults = {
             'name': lambda self, cr, uid, context = None: self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'),
             'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
    }

    def _check_procurement_for_service_with_recep(self, cr, uid, ids, context=None):
        """
        You cannot select Service Location as Source Location.
        """
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.type == 'service_recep' and obj.type != 'make_to_order':
                raise osv.except_osv(_('Error'), _('You must select on order procurement method for Service with Reception products.'))
        return True

    _constraints = [
        (_check_procurement_for_service_with_recep, 'You must select on order procurement method for Service with Reception products.', []),
    ]

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set the location_id with the stock location of the warehouse of the order of the line
        '''
        # Objects
        warehouse_obj = self.pool.get('stock.warehouse')

        res = super(sourcing_line, self).default_get(cr, uid, fields, context=context)

        if res is None:
            res = {}

        warehouse = warehouse_obj.search(cr, uid, [], context=context)
        if warehouse:
            res['location_id'] = warehouse_obj.browse(cr, uid, warehouse[0], context=context).lot_stock_id.id

        return res

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
            if line.type == 'make_to_order' and line.sale_order_id \
                    and line.sale_order_id.state != 'draft' \
                    and not context.get('fromOrderLine') \
                    and line.sale_order_id.order_type == 'loan':
                raise osv.except_osv(_('Warning'), _("""You can't source a loan 'from stock'."""))

            if line.type == 'make_to_order' and line.po_cft not in ['cft'] and not line.product_id and \
               line.sale_order_id.procurement_request and line.supplier and line.supplier.partner_type not in ['internal', 'section', 'intermission']:
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

            if line.sale_order_id and line.sale_order_id.procurement_request and line.type == 'make_to_stock':
                if line.sale_order_id.location_requestor_id.id == line.location_id.id:
                    raise osv.except_osv(_('Warning'), _("You cannot choose a source location which is the destination location of the Internal Request"))

        return True


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

    def open_split_wizard(self, cr, uid, ids, context=None):
        '''
        Open the split line wizard
        '''
        line = self.browse(cr, uid, ids[0], context=context)
        return self.pool.get('sale.order.line').open_split_wizard(cr, uid, [line.sale_order_line_id.id], context=context)

    def check_supplierinfo(self, cr, uid, ids, partner_id, context=None):
        '''
        return the value of delay if the corresponding supplier is in supplier info the product

        designed for one unique sourcing line as parameter (ids)
        '''
        for sourcing_line in self.browse(cr, uid, ids, context=context):
            delay = -1
            return sourcing_line.supplier and sourcing_line.supplier.supplier_lt or delay

    def write(self, cr, uid, ids, values, context=None):
        '''
        _name = 'sourcing.line'

        override write method to write back
         - po_cft
         - partner
         - type
        to sale order line
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Remove the saved estimated DD on cancellation of the FO line
        if 'state' in values and values['state'] == 'cancel':
            self.write(cr, uid, ids, {'cf_estimated_delivery_date': False}, context=context)

        if 'fromOrderLine' not in context and 'fromOrder' not in context:
            context['fromSourcingLine'] = True
            for sourcingLine in self.browse(cr, uid, ids, context=context):
                # values to be saved to *sale order line*
                vals = {}
                solId = sourcingLine.sale_order_line_id.id

                # type
                if 'type' in values:
                    l_type = values['type']
                    vals.update({'type': l_type})
                else:
                    l_type = sourcingLine.type
                    vals.update({'type': l_type})
                # pocft: if type == make_to_stock, pocft = False, otherwise modified value or saved value
                if l_type == 'make_to_order':
                    if 'po_cft' in values:
                        pocft = values['po_cft']
                        vals.update({'po_cft': pocft})
                        if pocft == 'cft':
                            # no supplier for tender
                            values.update({'supplier': False})
                            vals.update({'supplier': False})
                    values.update({'location_id': False})
                    vals.update({'location_id': False})
                else:
                    # if make to stock, reset anyway to False
                    pocft = False
                    values.update({'po_cft': pocft, 'supplier': False})
                    vals.update({'po_cft': pocft, 'supplier': False})

                # location_id
                if 'location_id' in values:
                    vals.update({'location_id': values['location_id']})

                # partner_id
                if 'supplier' in values:
                    partner_id = values['supplier']
                    vals.update({'supplier': partner_id})
                    # update the delivery date according to partner_id, only update from the sourcing tool
                    # not from order line as we dont want the date is udpated when the line's state changes for example
                    if partner_id:
                        # if a new partner_id has been selected update the *sourcing_line* -> values
                        partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context)

                        # if the selected partner belongs to product->suppliers, we take that delay (from supplierinfo)
                        delay = self.check_supplierinfo(cr, uid, [sourcingLine.id], partner_id, context=context)
                        # otherwise we take the default value from product form
                        if delay < 0:
                            delay = partner.default_delay

                        daysToAdd = delay
                        estDeliveryDate = date.today()
                        estDeliveryDate = estDeliveryDate + relativedelta(days=int(daysToAdd))
                        values.update({'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d')})
                    else:
                        # no partner is selected, erase the date
                        values.update({'estimated_delivery_date': False})

                # update sourcing line
                self.pool.get('sale.order.line').write(cr, uid, solId, vals, context=context)

        res = super(sourcing_line, self).write(cr, uid, ids, values, context=context)
        self._check_line_conditions(cr, uid, ids, context)
        return res

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

    def onChangeType(self, cr, uid, line_id, type, location_id=False, context=None):
        '''
        if type == make to stock, change pocft to False
        '''
        if not context:
            context = {}

        value = {}
        message = {}
        if line_id:
            line = self.browse(cr, uid, line_id, context=context)[0]
            if line.product_id.type in ('consu', 'service', 'service_recep') and type == 'make_to_stock':
                product_type = line.product_id.type == 'consu' and 'non stockable' or 'service'
                value.update({'type': 'make_to_order'})
                message.update({'title': _('Warning'),
                                'message': _('You cannot choose \'from stock\' as method to source a %s product !') % product_type})

        if type == 'make_to_stock':
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
                    res, error = self._check_product_constraints(cr, uid, type, line.po_cft, line.product_id.id, False, check_fnct, field_name='type', values=res, vals={'constraints': ['storage']}, context=context)
                    if error:
                        return res

        return {'value': value, 'warning': message}

    def onChangeSupplier(self, cr, uid, id, supplier, context=None):
        '''
        supplier changes, we update 'estimated_delivery_date' with corresponding delivery lead time
        we add a domain for the IR line on the supplier
        '''
        result = {'value':{}, 'domain':{}}

        if not supplier:
            for sl in self.browse(cr, uid, id, context):
                if not sl.product_id and sl.sale_order_id.procurement_request and sl.type == 'make_to_order':
                    result['domain'].update({'supplier': [('partner_type', 'in', ['internal', 'section', 'intermission'])]})
            return result

        partner = self.pool.get('res.partner').browse(cr, uid, supplier, context)
        # if the selected partner belongs to product->suppliers, we take that delay (from supplierinfo)
        delay = self.check_supplierinfo(cr, uid, id, partner.id, context=context)
        # otherwise we take the default value from product form
        if delay < 0:
            delay = partner.default_delay

        daysToAdd = delay
        estDeliveryDate = date.today()
        estDeliveryDate = estDeliveryDate + relativedelta(days=int(daysToAdd))

        result['value'].update({'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d')})

        if id and isinstance(id, list):
            id = id[0]

        line = self.browse(cr, uid, id, context=context)
        value = result['value']
        partner_id = 'supplier' in value and value['supplier'] or supplier
        if id and partner_id and line.product_id:
            check_fnct = self.pool.get('product.product')._on_change_restriction_error
            result, error = self._check_product_constraints(cr, uid, line.type, value.get('po_cft', line.po_cft), line.product_id.id, partner_id, check_fnct, field_name='supplier', values=result, vals={'partner_id': partner_id}, context=context)
            if error:
                return result

        return result

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy method from sourcing_line
        '''
        result = super(sourcing_line, self).copy(cr, uid, id, default, context)
        return result

    def create(self, cr, uid, vals, context=None):
        '''
        create method from sourcing_line
        '''
        res = super(sourcing_line, self).create(cr, uid, vals, context)
        self._check_line_conditions(cr, uid, res, context)
        return res

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        copy_data method for soucring_line
        '''
        if not default:
            default = {}

        if not context:
            context = {}
        # updated sequence number
        default.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'), })
        # get sale_order_id
#        if '__copy_data_seen' in context and 'sale.order' in context['__copy_data_seen'] and len(context['__copy_data_seen']['sale.order']) == 1:
#            soId = context['__copy_data_seen']['sale.order'][0]
#            default.update({'sale_order_id': soId,})

        return super(sourcing_line, self).copy_data(cr, uid, id, default, context=context)

    def confirmLine(self, cr, uid, ids, context=None):
        '''
        set the corresponding line's state to 'confirmed'
        if all lines are 'confirmed', the sale order is confirmed
        '''
        context = context or {}
        wf_service = netsvc.LocalService("workflow")
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


    def unconfirmLine(self, cr, uid, ids, context=None):
        '''
        set the sale order line state to 'draft'
        '''
        line_obj = self.pool.get('sale.order.line')
        wf_service = netsvc.LocalService("workflow")
        result = []
        for sl in self.browse(cr, uid, ids, context):
            result.append((sl.id, line_obj.write(cr, uid, sl.sale_order_line_id.id, {'state':'draft'}, context)))

        return result

sourcing_line()


class sale_order(osv.osv):

    _inherit = 'sale.order'
    _description = 'Sales Order'
    _columns = {'sourcing_line_ids': fields.one2many('sourcing.line', 'sale_order_id', 'Sourcing Lines'),
                'sourcing_trace_ok': fields.boolean(string='Display sourcing logs'),
                'sourcing_trace': fields.text(string='Sourcing logs', readonly=True),
                }

    def create(self, cr, uid, vals, context=None):
        '''
        create from sale_order
        '''
        return super(sale_order, self).create(cr, uid, vals, context)

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

                sourcing_ids = []
                # for each sale order line
                for sol in so.order_line:
                    # update the sourcing line
                    for sl in sol.sourcing_line_ids:
                        sourcing_ids.append(sl.id)

                self.pool.get('sourcing.line').write(cr, uid, sourcing_ids, sourcing_values, context)

        return super(sale_order, self).write(cr, uid, ids, vals, context)


    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy from sale_order

        dont copy sourcing lines, they are generated at sale order lines creation
        '''
        if not default:
            default = {}

        default['sourcing_line_ids'] = []
        default['sourcing_trace'] = ''
        default['sourcing_trace_ok'] = False

        return super(sale_order, self).copy(cr, uid, id, default, context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        _inherit = 'sale.order'


        override because of Bug #604347

        on_delete constraints are not generated

        remove manually all linked sourcing_line
        '''
        if not context:
            context = {}
        context.update({'fromSaleOrder': True})
        idsToDelete = []
        for order in self.browse(cr, uid, ids, context):
            for orderLine in order.order_line:
                for sourcingLine in orderLine.sourcing_line_ids:
                    idsToDelete.append(sourcingLine.id)

        self.pool.get('sourcing.line').unlink(cr, uid, idsToDelete, context)

        return super(sale_order, self).unlink(cr, uid, ids, context)

    def action_cancel(self, cr, uid, ids, context=None):
        '''
        Don't check line integrity
        '''
        if not context:
            context = {}

        context.update({'no_check_line': True})

        return super(sale_order, self).action_cancel(cr, uid, ids, context=context)

    def _hook_ship_create_procurement_order(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py

        - allow to modify the data for procurement order creation
        '''
        result = super(sale_order, self)._hook_ship_create_procurement_order(cr, uid, ids, context=context, *args, **kwargs)
        proc_data = kwargs['proc_data']
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
    '''
    override of sale_order_line class
    creation/update/copy of sourcing_line
    '''
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'
    _columns = {
                'po_cft': fields.selection(_SELECTION_PO_CFT, string="PO/CFT"),
                'supplier': fields.many2one('res.partner', 'Supplier'),
                'sourcing_line_ids': fields.one2many('sourcing.line', 'sale_order_line_id', 'Sourcing Lines'),
                'location_id': fields.many2one('stock.location', string='Location'),
                }

    def create(self, cr, uid, vals, context=None):
        '''
        _inherit = 'sale.order.line'

        override create method, create corresponding sourcing.line objects

        vals > dict: {
        'property_ids': [(6, 0, [])],
        'product_uos_qty': 1.0,
        'name': '[PC1] Basic PC',
        'product_uom': 1,
        'order_id': 14,
        'notes': False,
        'product_uom_qty': 1.0,
        'delay': 2.0,
        'discount': 0.0,
        'product_id': 3,
        'th_weight': 0.0,
        'product_uos': False,
        'product_packaging': False,
        'tax_id': [(6, 0, [])],
        'type': 'make_to_stock',
        'price_unit': 450.0,
        'address_allotment_id': False,
        'customer': partner_id,
        }
        '''
        if not context:
            context = {}
        # if a product has been selected, get supplier default value
        sellerId = vals.get('supplier')
        deliveryDate = False

        if vals.get('order_id'):
            # If the line is created after the validation of the FO, and if the FO is a loan
            # Force the sourcing type 'from stock'
            order = self.pool.get('sale.order').browse(cr, uid, vals.get('order_id'), context=context)
            if order.order_type == 'loan' and order.state == 'validated':
                vals['type'] = 'make_to_stock'
                vals['po_cft'] = False
                vals['supplier'] = False
                sellerId = False

        if vals.get('type') == 'make_to_order' and vals.get('product_id'):
            ctx = context.copy()
            if sellerId:
                ctx['delay_supplier_id'] = sellerId

            product = self.pool.get('product.product').browse(cr, uid, vals['product_id'], ctx)

            if not sellerId:
                seller = product.seller_id
                sellerId = (seller and seller.id) or False

                if sellerId:
                    deliveryDate = int(product.seller_delay)
            else:
                deliveryDate = product.delay_for_supplier

        # if type is missing, set to make_to_stock and po_cft to False
        if not vals.get('type'):
            vals['type'] = 'make_to_stock'
            vals['po_cft'] = False

        if vals.get('product_id', False):
            bropro = self.pool.get('product.product').browse(cr, uid, vals['product_id'])
            if bropro.type in ('consu', 'service', 'service_recep'):
                vals['type'] = 'make_to_order'

        # fill po/cft : by default, if mto -> po and po_cft is not specified in data, if mts -> False
        if not vals.get('po_cft', False) and vals.get('type', False) == 'make_to_order':
            vals['po_cft'] = 'po'
        elif vals.get('type', False) == 'make_to_stock':
            vals['po_cft'] = False

        # fill the supplier
        vals.update({'supplier': sellerId})

        # create the new sale order line
        result = super(sale_order_line, self).create(cr, uid, vals, context=context)

        # delivery date : supplier lead-time and 2 days for administrative treatment
        estDeliveryDate = False
        if deliveryDate:
            daysToAdd = deliveryDate
            estDeliveryDate = date.today()
            estDeliveryDate = estDeliveryDate + relativedelta(days=int(daysToAdd))
            estDeliveryDate = estDeliveryDate.strftime('%Y-%m-%d')

        # order state
        order = self.pool.get('sale.order').browse(cr, uid, vals['order_id'], context)
        orderState = order.state_hidden_sale_order
        orderPriority = order.priority
        orderCategory = order.categ
        customer_id = order.partner_id.id

        if sellerId:
            seller = self.pool.get('res.partner').browse(cr, uid, sellerId)
            if seller.partner_type and not order.procurement_request and not seller.partner_type in ['external', 'esc']:
                sellerId = False

        values = {
                  'sale_order_id': vals['order_id'],
                  'sale_order_line_id': result,
                  'customer_id': customer_id,
                  'supplier': sellerId,
                  'po_cft': vals['po_cft'],
                  'estimated_delivery_date': estDeliveryDate,
                  'rts': time.strftime('%Y-%m-%d'),
                  'type': vals['type'],
                  'line_number': vals['line_number'],
                  'product_id': vals.get('product_id', False),
                  'priority': orderPriority,
                  'categ': orderCategory,
                  'sale_order_state': orderState,
                  'state': self.browse(cr, uid, result, context=context).state
                  }

        sourcing_line_id = self.pool.get('sourcing.line').create(cr, uid, values, context=context)
        # update sourcing line - trigger update of fields.function values -- OPENERP BUG ? with empty values
        self.pool.get('sourcing.line').write(cr, uid, [sourcing_line_id], {}, context=context)

        return result

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy from sale order line
        '''
        if not context:
            context = {}

        result = super(sale_order_line, self).copy(cr, uid, id, default, context)
        return result

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        copy_data from sale order line

        dont copy sourcing lines, they are generated at sale order lines creation
        '''
        if not default:
            default = {}
        default.update({'sourcing_line_ids': []})

        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)

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
        sourcing_obj = self.pool.get('sourcing.line')
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if vals.get('product_id', False):
            bropro = self.pool.get('product.product').browse(cr, uid, vals['product_id'])
            if bropro.type in ('consu', 'service', 'service_recep'):
                vals['type'] = 'make_to_order'

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
            loan_sl_ids = sourcing_obj.search(cr, uid, [('sale_order_line_id', 'in', loan_sol_ids)], context=context)

            # Other lines to modified with standard values
            sol_ids = self.search(cr, uid, [('id', 'in', ids), ('id', 'not in', loan_sol_ids)], context=context)
            sl_ids = sourcing_obj.search(cr, uid, [('sale_order_line_id', 'in', sol_ids)], context=context)

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
                    self.pool.get('sourcing.line').write(cr, uid, loan_sl_ids, loan_values, context)

                if loan_sol_ids:
                    # Update lines with loan
                    result = super(sale_order_line, self).write(cr, uid, loan_sol_ids, loan_vals, context)

            if sl_ids and values:
                # Update other sourcing lines
                self.pool.get('sourcing.line').write(cr, uid, sl_ids, values, context)
            if sol_ids and vals:
                # Update other lines
                result = super(sale_order_line, self).write(cr, uid, sol_ids, vals, context)
        else:
            # Just call the parent write()
            result = super(sale_order_line, self).write(cr, uid, ids, vals, context)

        return result

    def unlink(self, cr, uid, ids, context=None):
        '''
        _inherit = 'sale.order.line'


        override because of Bug #604347

        on_delete constraints are not generated

        remove manually all linked sourcing_line
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        context.update({'fromSaleOrderLine': True})
        idsToDelete = []
        for orderLine in self.browse(cr, uid, ids, context):
            for sourcingLine in orderLine.sourcing_line_ids:
                idsToDelete.append(sourcingLine.id)
        # delete sourcing lines
        self.pool.get('sourcing.line').unlink(cr, uid, idsToDelete, context)

        return super(sale_order_line, self).unlink(cr, uid, ids, context)

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
        type = 'type' in result['value'] and result['value']['type']
        if product and type:
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            seller = productObj.seller_id
            sellerId = (seller and seller.id) or False

            if type == 'make_to_order':
                po_cft = 'po'

            result['value'].update({'supplier': sellerId, 'po_cft': po_cft})

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
        for id in ids:
            result[id] = []
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
        for id in ids:
            result[id] = False
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
                    sl = self.pool.get('sourcing.line').browse(cr, uid, active_id)[0]
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
        partner_obj = self.pool.get('res.partner')
        local_market = None
        # Search the local market partner id
        data_obj = self.pool.get('ir.model.data')
        data_id = data_obj.search(cr, uid, [('module', '=', 'order_types'), ('model', '=', 'res.partner'), ('name', '=', 'res_partner_local_market')])
        if data_id:
            local_market = data_obj.read(cr, uid, data_id, ['res_id'])[0]['res_id']
        for arg in args:
            if arg[0] == 'check_partner_po':
                if arg[1] != '=' \
                or arg[2]['order_type'] not in ['regular', 'donation_exp', 'donation_st', 'loan', 'in_kind', 'purchase_list', 'direct']\
                or not isinstance(arg[2]['partner_id'], (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter check_partner_po different than (arg[0], =, %s) not implemented.') % arg[2])
                partner_id = arg[2]['partner_id']
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
                # Useless code because if we enter in direct case, we do not enter in this one
#                elif partner_id and partner_id != local_market:
#                    partner = partner_obj.browse(cr, uid, partner_id)
#                    if partner.partner_type not in ('external', 'esc') and order_type == 'direct':
#                        newargs.append(('partner_type', 'in', ['esc', 'external']))
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
