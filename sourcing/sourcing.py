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

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time

from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from sale_override import SALE_ORDER_STATE_SELECTION

_SELECTION_PO_CFT = [
                     ('po', 'Purchase Order'),
                     ('dpo', 'Direct Purchase Order'),
                     ('cft', 'Tender'),
                     ]

class sourcing_line(osv.osv):
    '''
    Class for sourcing_line
    
    sourcing lines are generated when a Sale Order is created
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
    
    def _getVirtualStock(self, cr, uid, ids, field_names=None, arg=False, context=None):
        '''
        get virtual stock (virtual_available) for the product of the corresponding sourcing line
        where date of stock.move is smaller than or equal to rts
        '''
        result = {}
        productObj = self.pool.get('product.product')
        # for each sourcing line
        for sl in self.browse(cr, uid, ids, context):
            rts = sl.rts
            productId = sl.product_id.id
            if productId:
                productList = [productId]
            else:
                productList = []
            res = productObj.get_product_available(cr, uid, productList, context={'states': ('confirmed','waiting','assigned','done'),
                                                                                  'what': ('in', 'out'),
                                                                                  'to_date': rts})
            result[sl.id] = res.get(productId, 0.0)
            
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
                result[obj.id].update({f: False,})
            # gather procurement_request boolean
            result[obj.id]['procurement_request'] = obj.sale_order_id and obj.sale_order_id.procurement_request or False
            # gather sale order line state
            result[obj.id]['state'] = obj.sale_order_line_id and obj.sale_order_line_id.state or False
            # display confirm button - display if state == draft and not proc or state == progress and proc
            result[obj.id]['display_confirm_button'] = (obj.state == 'draft' and obj.sale_order_id.state == 'validated')
        
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
        ids represents the ids of sale.order.line objects for which state has changed
        
        return the list of ids of sourcing.line object which need to get their state field updated
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # list of sourcing lines having sale_order_line_id within ids
        result = self.pool.get('sourcing.line').search(cr, uid, [('sale_order_line_id', 'in', ids)], context=context)
        return result
    
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
        for id in ids:
            result[id] = False
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
            
            tr_lt = line.sale_order_id and line.sale_order_id.est_transport_lead_time or 0.00
            ship_lt = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.shipment_lead_time
            res[line.id]['rts'] = datetime.strptime(line.sale_order_line_id.date_planned, '%Y-%m-%d') - relativedelta(days=int(tr_lt)) - relativedelta(days=int(ship_lt))
            res[line.id]['rts'] = res[line.id]['rts'].strftime('%Y-%m-%d')
        
        return res

    _columns = {
        # sequence number
        'name': fields.char('Name', size=128),
        'sale_order_id': fields.many2one('sale.order', 'Sale Order', on_delete='cascade', readonly=True),
        'sale_order_line_id': fields.many2one('sale.order.line', 'Sale Order Line', on_delete='cascade', readonly=True),
        'customer': fields.many2one('res.partner', 'Customer', readonly=True),
        'reference': fields.related('sale_order_id', 'name', type='char', size=128, string='Reference', readonly=True),
#        'state': fields.related('sale_order_line_id', 'state', type="selection", selection=_SELECTION_SALE_ORDER_LINE_STATE, readonly=True, string="State", store=False),
        'state': fields.function(_get_sourcing_vals, method=True, type='selection', selection=_SELECTION_SALE_ORDER_LINE_STATE, string='State', multi='get_vals_sourcing',
                                  store={'sale.order.line': (_get_sale_order_line_ids, ['state'], 10),
                                         'sourcing.line': (_get_souring_lines_ids, ['sale_order_line_id'], 10)}),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True),
        'categ': fields.selection(ORDER_CATEGORY, string='Category', readonly=True),
        'sale_order_state': fields.selection(_SELECTION_SALE_ORDER_STATE, string="Order State", readonly=True),
        'sale_order_state_search': fields.function(_get_fake, string="Order State", type='selection', method=True, selection=[x for x in SALE_ORDER_STATE_SELECTION if x[0] != 'manual'], fnct_search=_search_sale_order_state),
        'line_number': fields.integer(string='Line', readonly=True),
        'product_id': fields.many2one('product.product', string='Product', readonly=True),
        'qty': fields.related('sale_order_line_id', 'product_uom_qty', type='float', string='Quantity', readonly=True),
        'uom_id': fields.related('sale_order_line_id', 'product_uom', relation='product.uom', type='many2one', string='UoM', readonly=True),
        #'rts': fields.related('sale_order_id', 'ready_to_ship_date', type='date', string='RTS', readonly=True),
        'rts': fields.function(_get_date, type='date', method=True, string='RTS', readonly=True, store=False, multi='dates'),
        'sale_order_line_state': fields.related('sale_order_line_id', 'state', type="selection", selection=_SELECTION_SALE_ORDER_LINE_STATE, readonly=True, store=False),
        'type': fields.selection(_SELECTION_TYPE, string='Procurement Method', readonly=True, states={'draft': [('readonly', False)]}),
        'po_cft': fields.selection(_SELECTION_PO_CFT, string='PO/CFT', readonly=True, states={'draft': [('readonly', False)]}),
        'real_stock': fields.related('product_id', 'qty_available', type='float', string='Real Stock', readonly=True),
        'available_stock': fields.float('Available Stock', readonly=True),
        'virtual_stock': fields.function(_getVirtualStock, method=True, type='float', string='Virtual Stock', digits_compute=dp.get_precision('Product UoM'), readonly=True),
        'supplier': fields.many2one('res.partner', 'Supplier', readonly=True, states={'draft': [('readonly', False)]}, domain=[('supplier', '=', True)]),
        'cf_estimated_delivery_date': fields.date(string='Estimated DD', readonly=True),
        'estimated_delivery_date': fields.function(_get_date, type='date', method=True, store=False, string='Estimated DD', readonly=True, multi='dates'),
        'company_id': fields.many2one('res.company','Company',select=1),
        'procurement_request': fields.function(_get_sourcing_vals, method=True, type='boolean', string='Procurement Request', multi='get_vals_sourcing',
                                               store={'sale.order': (_get_sale_order_ids, ['procurement_request'], 10),
                                                      'sourcing.line': (_get_souring_lines_ids, ['sale_order_id'], 10)}),
        'display_confirm_button': fields.function(_get_sourcing_vals, method=True, type='boolean', string='Display Button', multi='get_vals_sourcing',),
        'need_sourcing': fields.function(_get_fake, method=True, type='boolean', string='Only for filtering', fnct_search=_search_need_sourcing),
    }
    _order = 'sale_order_id desc, line_number'
    _defaults = {
             'name': lambda self, cr, uid, context=None: self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'),
             'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
    }
    
    def check_supplierinfo(self, cr, uid, ids, partner_id, context=None):
        '''
        return the value of delay if the corresponding supplier is in supplier info the product
        
        designed for one unique sourcing line as parameter (ids)
        '''
        for sourcing_line in self.browse(cr, uid, ids, context=context):
            delay = -1
            for suppinfo in sourcing_line.product_id.seller_ids:
                if suppinfo.name.id == partner_id:
                    delay = suppinfo.delay
                    
            return delay
    
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
            context={}
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
                    type = values['type']
                    vals.update({'type': type})
                else:
                    type = sourcingLine.type
                    vals.update({'type': type})
                # pocft: if type == make_to_stock, pocft = False, otherwise modified value or saved value
                if type == 'make_to_order':
                    if 'po_cft' in values:
                        pocft = values['po_cft']
                        vals.update({'po_cft': pocft})
                else:
                    # if make to stock, reset anyway to False
                    pocft = False
                    values.update({'po_cft': pocft, 'supplier': False})
                    vals.update({'po_cft': pocft, 'supplier': False})
                
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
        
        return super(sourcing_line, self).write(cr, uid, ids, values, context=context)
    
    def onChangeType(self, cr, uid, id, type, context=None):
        '''
        if type == make to stock, change pocft to False
        '''
        value = {}
        if type == 'make_to_stock':
            value.update({'po_cft': False})
    
        return {'value': value}
    
    def onChangeSupplier(self, cr, uid, id, supplier, context=None):
        '''
        supplier changes, we update 'estimated_delivery_date' with corresponding delivery lead time
        '''
        result = {'value':{}}
        
        if not supplier:
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
        result = super(sourcing_line, self).create(cr, uid, vals, context)
        return result
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        copy_data method for soucring_line
        '''
        if not default:
            default = {}
            
        if not context:
            context = {}
        # updated sequence number
        default.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'sourcing.line'),})
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
        wf_service = netsvc.LocalService("workflow")
        result = []
        for sl in self.browse(cr, uid, ids, context):
            # check if it is in On Order and if the Supply info is valid, if it's empty, just exit the action
            
            if sl.type == 'make_to_order' and sl.po_cft in ('po', 'dpo') and not sl.supplier:
                raise osv.except_osv(_('Warning'), _("The supplier must be chosen before confirming the line"))
            
            # set the corresponding sale order line to 'confirmed'
            result.append((sl.id, sl.sale_order_line_id.write({'state':'confirmed'}, context)))
            # check if all order lines have been confirmed
            linesConfirmed = True
            for ol in sl.sale_order_id.order_line:
                if ol.state != 'confirmed':
                    linesConfirmed = False
                    break
                
            # if all lines have been confirmed, we confirm the sale order
            if linesConfirmed:
                if sl.sale_order_id.procurement_request:
                    wf_service.trg_validate(uid, 'sale.order', sl.sale_order_id.id, 'procurement_confirm', cr)
                else:
                    wf_service.trg_validate(uid, 'sale.order', sl.sale_order_id.id, 'order_confirm', cr)
            
            self.write(cr, uid, [sl.id], {'cf_estimated_delivery_date': sl.estimated_delivery_date}, context=context)
                
        return result
    
    def unconfirmLine(self, cr, uid, ids, context=None):
        '''
        set the sale order line state to 'draft'
        '''
        wf_service = netsvc.LocalService("workflow")
        result = []
        for sl in self.browse(cr, uid, ids, context):
            result.append((sl.id, sl.sale_order_line_id.write(cr, uid, sl.sale_order_line_id.id, {'state':'draft'}, context)))
                
        return result
        
sourcing_line()

class sale_order(osv.osv):
    
    _inherit = 'sale.order'
    _description = 'Sales Order'
    _columns = {'sourcing_line_ids': fields.one2many('sourcing.line', 'sale_order_id', 'Sourcing Lines'),
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
        values = {}
        if 'priority' in vals:
            values.update({'priority': vals['priority']})
        if 'categ' in vals:
            values.update({'categ': vals['categ']})
        if 'state' in vals:
            values.update({'sale_order_state': vals['state']})
        
        # for each sale order
        for so in self.browse(cr, uid, ids, context):
            # for each sale order line
            for sol in so.order_line:
                # update the sourcing line
                for sl in sol.sourcing_line_ids:
                    self.pool.get('sourcing.line').write(cr, uid, sl.id, values, context)
                    if vals.get('partner_id') and vals.get('partner_id') != so.partner_id.id:
                        self.pool.get('sourcing.line').write(cr, uid, sl.id, {'customer': so.partner_id.id}, context)
        
        return super(sale_order, self).write(cr, uid, ids, vals, context)
        
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy from sale_order
        
        dont copy sourcing lines, they are generated at sale order lines creation
        '''
        if not default:
            default={}
            
        default['sourcing_line_ids']=[]
        
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
        # uf-583 - the location defined for the procurementis input instead of stock
        order = kwargs['order']
        result['location_id'] = order.shop_id.warehouse_id.lot_input_id.id,

        return result

    def _hook_procurement_create_line_condition(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
             
        - allow to customize the execution condition
        '''
        line = kwargs['line']
        
        if line.type == 'make_to_stock' and line.order_id.procurement_request:
            return False

        return True

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

        # type
        if not vals.get('type'):
            vals['type'] = 'make_to_stock'
        
        # fill po/cft : by default, if mto -> po, if mts -> False
        pocft = False
        if vals['type'] == 'make_to_order':
            pocft = 'po'
        
        # fill the default pocft and supplier
        vals.update({'po_cft': pocft})
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
        orderState = order.state
        orderPriority = order.priority
        orderCategory = order.categ
        customer_id = order.partner_id.id
        
        values = {
                  'sale_order_id': vals['order_id'],
                  'sale_order_line_id': result,
                  'customer_id': customer_id,
                  'supplier': sellerId,
                  'po_cft': pocft,
                  'estimated_delivery_date': estDeliveryDate,
                  'rts': time.strftime('%Y-%m-%d'),
                  'type': vals['type'],
                  'line_number': vals['line_number'],
                  'product_id': vals['product_id'],
                  'priority': orderPriority,
                  'categ': orderCategory,
                  'sale_order_state': orderState,
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
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]

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
                
            # for each sale order line
            for sol in self.browse(cr, uid, ids, context):
                # for each sourcing line
                for sourcingLine in sol.sourcing_line_ids:
                    self.pool.get('sourcing.line').write(cr, uid, sourcingLine.id, values, context)
        
        result = super(sale_order_line, self).write(cr, uid, ids, vals, context)
        return result
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        _inherit = 'sale.order.line'
        
        
        override because of Bug #604347
        
        on_delete constraints are not generated
        
        remove manually all linked sourcing_line
        '''
        if not context:
            context = {}
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
    
    def action_check_finished(self, cr, uid, ids):
        res = super(procurement_order, self).action_check_finished(cr, uid, ids)
        
        # If the procurement has been generated from an internal request, close the order
        for order in self.browse(cr, uid, ids):
            line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', order.id)])
            for line in self.pool.get('sale.order.line').browse(cr, uid, line_ids):
                if line.order_id.procurement_request:
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

        partner = self.pool.get('res.partner').browse(cr, uid, values['partner_id'], context=context)
        
        purchase_domain = [('partner_id', '=', partner.id),
                           ('state', '=', 'draft'),
                           ('delivery_requested_date', '=', values.get('delivery_requested_date'))]
        
        if procurement.po_cft == 'dpo':
            purchase_domain.append(('order_type', '=', 'direct'))
        else:
            purchase_domain.append(('order_type', '!=', 'direct'))
        
        if partner.po_by_project == 'project' or procurement.po_cft == 'dpo':
            sale_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
            customer_id = self.pool.get('sale.order.line').browse(cr, uid, sale_line_ids[0], context=context).order_id.partner_id.id
            values.update({'customer_id': customer_id})
            purchase_domain.append(('customer_id', '=', customer_id))
            
        purchase_ids = po_obj.search(cr, uid, purchase_domain, context=context)
            
        if purchase_ids:
            line_values = values['order_line'][0][2]
            line_values.update({'order_id': purchase_ids[0]})
            purchase = po_obj.browse(cr, uid, purchase_ids[0], context=context)
            if not purchase.origin_tender_id or not purchase.origin_tender_id.sale_order_id or purchase.origin_tender_id.sale_order_id.name != procurement.origin:
                origin = procurement.origin in purchase.origin and purchase.origin or '%s/%s' % (purchase.origin, procurement.origin)
                po_obj.write(cr, uid, [purchase_ids[0]], {'origin': origin}, context=context)
            self.pool.get('purchase.order.line').create(cr, uid, line_values, context=context)
            return purchase_ids[0]
        else:
            if procurement.po_cft == 'dpo':
                sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
                sol = self.pool.get('sale.order.line').browse(cr, uid, sol_ids[0], context=context)
                values.update({'order_type': 'direct', 
                               'dest_partner_id': sol.order_id.partner_id.id, 
                               'dest_address_id': sol.order_id.partner_shipping_id.id})
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
        tender_line_obj = self.pool.get('tender_line')
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
        if isinstance(ids,(long, int)):
            ids = [ids]
        
        result = {}
        for id in ids:
            result[id] = False
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
    
    _columns = {'product_product_ids': fields.function(_get_false, method=True, type='one2many',relation='product.product', string="Products",fnct_search=_get_product_ids),
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
