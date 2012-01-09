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

from osv import osv, fields
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from tools.translate import _
import netsvc

from mx.DateTime import *

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def copy(self, cr, uid, id, default, context={}):
        '''
        Remove loan_id field on new purchase.order
        '''
        return super(purchase_order, self).copy(cr, uid, id, default={'loan_id': False}, context=context)
    
    # @@@purchase.purchase_order._invoiced
    def _invoiced(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for purchase in self.browse(cursor, user, ids, context=context):
            invoiced = False
            if purchase.invoiced_rate == 100.00:
                invoiced = True
            res[purchase.id] = invoiced
        return res
    # @@@end
    
    # @@@purchase.purchase_order._shipped_rate
    def _invoiced_rate(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for purchase in self.browse(cursor, user, ids, context=context):
            if ((purchase.order_type == 'regular' and purchase.partner_id.partner_type == 'internal') or \
                purchase.order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']):
                res[purchase.id] = purchase.shipped_rate
            else:
                tot = 0.0
                for invoice in purchase.invoice_ids:
                    if invoice.state not in ('draft','cancel'):
                        tot += invoice.amount_untaxed
                if purchase.amount_untaxed:
                    res[purchase.id] = min(100.0, tot * 100.0 / (purchase.amount_untaxed))
                else:
                    res[purchase.id] = 0.0
        return res
    # @@@end
    
    _columns = {
        'partner_id':fields.many2one('res.partner', 'Supplier', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}, change_default=True, domain="[('id', '!=', company_id)]"),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                        ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                        ('direct', 'Direct Purchase Order')], string='Order Type', required=True, states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'loan_id': fields.many2one('sale.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'details': fields.char(size=30, string='Details', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'invoiced': fields.function(_invoiced, method=True, string='Invoiced & Paid', type='boolean', help="It indicates that an invoice has been paid"),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'date_order':fields.date('Creation Date', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)], 'done':[('readonly',True)]}, select=True, help="Date on which this document has been created."),
        'name': fields.char('Order Reference', size=64, required=True, select=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)], 'done':[('readonly',True)]},
                            help="unique number of the purchase order,computed automatically when the purchase order is created"),
        'invoice_ids': fields.many2many('account.invoice', 'purchase_invoice_rel', 'purchase_id', 'invoice_id', 'Invoices', help="Invoices generated for a purchase order", readonly=True),
        'order_line': fields.one2many('purchase.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft':[('readonly',False)], 'rfq_sent':[('readonly',False)], 'confirmed': [('readonly',False)]}),
        'partner_id':fields.many2one('res.partner', 'Supplier', required=True, states={'rfq_sent':[('readonly',True)], 'rfq_done':[('readonly',True)], 'rfq_updated':[('readonly',True)], 'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}, change_default=True),
        'partner_address_id':fields.many2one('res.partner.address', 'Address', required=True,
            states={'rfq_sent':[('readonly',True)], 'rfq_done':[('readonly',True)], 'rfq_updated':[('readonly',True)], 'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]},domain="[('partner_id', '=', partner_id)]"),
        'merged_line_ids': fields.one2many('purchase.order.merged.line', 'order_id', string='Merged line'),
    }
    
    _defaults = {
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'other',
        'loan_duration': 2,
    }

    def _check_user_company(self, cr, uid, company_id, context={}):
        '''
        Remove the possibility to make a PO to user's company
        '''
        user_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        if company_id == user_company_id:
            raise osv.except_osv(_('Error'), _('You cannot made a purchase order to your own company !'))

        return True

    def create(self, cr, uid, vals, context={}):
        '''
        Check if the partner is correct
        '''
        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)
    
        return super(purchase_order, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context={}):
        '''
        Check if the partner is correct
        '''
        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)

        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)
    
    def onchange_internal_type(self, cr, uid, ids, order_type, partner_id):
        '''
        Changes the invoice method of the purchase order according to
        the choosen order type
        Changes the partner to local market if the type is Purchase List
        '''
        partner_obj = self.pool.get('res.partner')
        v = {}
        local_market = None
        
        # Search the local market partner id
        data_obj = self.pool.get('ir.model.data')
        data_id = data_obj.search(cr, uid, [('module', '=', 'order_types'), ('model', '=', 'res.partner'), ('name', '=', 'res_partner_local_market')] )
        if data_id:
            local_market = data_obj.read(cr, uid, data_id, ['res_id'])[0]['res_id']
        
        if order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']:
            v['invoice_method'] = 'manual'

        if partner_id and partner_id != local_market:
            partner = partner_obj.browse(cr, uid, partner_id)
            if partner.partner_type == 'internal' and order_type == 'regular':
                v['invoice_method'] = 'manual'
        elif partner_id and partner_id == local_market and order_type != 'purchase_list':
            v['partner_id'] = None
            v['dest_address_id'] = None
            v['partner_address_id'] = None
            v['pricelist_id'] = None
            
        if order_type == 'purchase_list':
            if local_market:
                partner = self.pool.get('res.partner').browse(cr, uid, local_market)
                v['partner_id'] = partner.id
                if partner.address:
                    v['dest_address_id'] = partner.address[0].id
                    v['partner_address_id'] = partner.address[0].id
                if partner.property_product_pricelist_purchase:
                    v['pricelist_id'] = partner.property_product_pricelist_purchase.id
        
        return {'value': v}
    
    def onchange_partner_id(self, cr, uid, ids, part):
        '''
        Fills the Requested and Confirmed delivery dates
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, part)
        
        if part:
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.browse(cr, uid, part)
            if partner.partner_type == 'internal':
                res['value']['invoice_method'] = 'manual'
        
        return res
    
    def wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        Checks if the invoice should be create from the purchase order
        or not
        '''
        line_obj = self.pool.get('purchase.order.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for order in self.browse(cr, uid, ids):
            if order.partner_id.partner_type == 'internal' and order.order_type == 'regular' or \
                         order.order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']:
                self.write(cr, uid, [order.id], {'invoice_method': 'manual'})
                line_obj.write(cr, uid, [x.id for x in order.order_line], {'invoiced': 1})
            
        return super(purchase_order, self).wkf_approve_order(cr, uid, ids, context=context)
    
    def action_sale_order_create(self, cr, uid, ids, context={}):
        '''
        Create a sale order as counterpart for the loan.
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        sale_obj = self.pool.get('sale.order')
        sale_line_obj = self.pool.get('sale.order.line')
        sale_shop = self.pool.get('sale.shop')
        partner_obj = self.pool.get('res.partner')
            
        for order in self.browse(cr, uid, ids):
            loan_duration = Parser.DateFromString(order.minimum_planned_date) + RelativeDateTime(months=+order.loan_duration)
            order_id = sale_obj.create(cr, uid, {'shop_id': sale_shop.search(cr, uid, [])[0],
                                                 'partner_id': order.partner_id.id,
                                                 'partner_order_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['contact'])['contact'],
                                                 'partner_invoice_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['invoice'])['invoice'],
                                                 'partner_shipping_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['delivery'])['delivery'],
                                                 'pricelist_id': order.partner_id.property_product_pricelist.id,
                                                 'loan_id': order.id,
                                                 'loan_duration': order.loan_duration,
                                                 'origin': order.name,
                                                 'order_type': 'loan',
                                                 'delivery_requested_date': loan_duration.strftime('%Y-%m-%d'),
                                                 'categ': order.categ,
                                                 'priority': order.priority,})
            for line in order.order_line:
                sale_line_obj.create(cr, uid, {'product_id': line.product_id and line.product_id.id or False,
                                               'product_uom': line.product_uom.id,
                                               'order_id': order_id,
                                               'price_unit': line.price_unit,
                                               'product_uom_qty': line.product_qty,
                                               'date_planned': loan_duration.strftime('%Y-%m-%d'),
                                               'delay': 60.0,
                                               'name': line.name,
                                               'type': line.product_id.procure_method})
            self.write(cr, uid, [order.id], {'loan_id': order_id})
            
            sale = sale_obj.browse(cr, uid, order_id)
            
            message = _("Loan counterpart '%s' was created.") % (sale.name,)
            
            sale_obj.log(cr, uid, order_id, message)
        
        return order_id
    
    def has_stockable_product(self,cr, uid, ids, *args):
        '''
        Override the has_stockable_product to return False
        when the order_type of the order is 'direct'
        '''
        # TODO: See with Synchro team which object the system will should create
        # to have an Incoming Movement in the destination instance
        for order in self.browse(cr, uid, ids):
            if order.order_type != 'direct':
                return super(purchase_order, self).has_stockable_product(cr, uid, ids, args)
        
        return False
    
    def action_invoice_create(self, cr, uid, ids, *args):
        '''
        Override this method to check the purchase_list box on invoice
        when the invoice comes from a purchase list
        '''
        invoice_id = super(purchase_order, self).action_invoice_create(cr, uid, ids, args)
        invoice_obj = self.pool.get('account.invoice')
        
        for order in self.browse(cr, uid, ids):
            if order.order_type == 'purchase_list':
                invoice_obj.write(cr, uid, [invoice_id], {'purchase_list': 1})
        
        return invoice_id
    
    def _hook_action_picking_create_modify_out_source_loc_check(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_picking_create method from purchase>purchase.py>purchase_order class
        
        - allow to choose whether or not the source location of the corresponding outgoing stock move should
        match the destination location of incoming stock move
        '''
        order_line = kwargs['order_line']
        # by default, we change the destination stock move if the destination stock move exists
        return order_line.move_dest_id
    
    # @@@override@purchase.purchase.order.action_picking_create
    def action_picking_create(self,cr, uid, ids, context={}, *args):
        picking_id = False
        for order in self.browse(cr, uid, ids):
            loc_id = order.partner_id.property_stock_supplier.id
            istate = 'none'
            reason_type_id = False
            if order.invoice_method=='picking':
                istate = '2binvoiced'
                
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.in')
            picking_values = {
                'name': pick_name,
                'origin': order.name+((order.origin and (':'+order.origin)) or ''),
                'type': 'in',
                'address_id': order.dest_address_id.id or order.partner_address_id.id,
                'invoice_state': istate,
                'purchase_id': order.id,
                'company_id': order.company_id.id,
                'move_lines' : [],
            }
            
            if order.order_type in ('regular', 'purchase_list', 'direct'):
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
            if order.order_type == 'loan':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
            if order.order_type == 'donation_st':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
            if order.order_type == 'donation_exp':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
            if order.order_type == 'in_kind':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_in_kind_donation')[1]
                
            if reason_type_id:
                picking_values.update({'reason_type_id': reason_type_id})
            
            picking_id = self.pool.get('stock.picking').create(cr, uid, picking_values, context=context)
            todo_moves = []
            for order_line in order.order_line:
                if not order_line.product_id:
                    continue
                if order_line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    dest = order.location_id.id
                    move_values = {
                        'name': order.name + ': ' +(order_line.name or ''),
                        'product_id': order_line.product_id.id,
                        'product_qty': order_line.product_qty,
                        'product_uos_qty': order_line.product_qty,
                        'product_uom': order_line.product_uom.id,
                        'product_uos': order_line.product_uom.id,
                        'date': order_line.date_planned,
                        'date_expected': order_line.date_planned,
                        'location_id': loc_id,
                        'location_dest_id': dest,
                        'picking_id': picking_id,
                        'move_dest_id': order_line.move_dest_id.id,
                        'state': 'draft',
                        'purchase_line_id': order_line.id,
                        'company_id': order.company_id.id,
                        'price_unit': order_line.price_unit
                    }
                    
                    if reason_type_id:
                        move_values.update({'reason_type_id': reason_type_id})
                    
                    move = self.pool.get('stock.move').create(cr, uid, move_values, context=context)
                    if self._hook_action_picking_create_modify_out_source_loc_check(cr, uid, ids, context=context, order_line=order_line,):
                        self.pool.get('stock.move').write(cr, uid, [order_line.move_dest_id.id], {'location_id':order.location_id.id})
                    todo_moves.append(move)
            self.pool.get('stock.move').action_confirm(cr, uid, todo_moves)
            self.pool.get('stock.move').force_assign(cr, uid, todo_moves)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id
        # @@@end
    
purchase_order()


class purchase_order_merged_line(osv.osv):
    _name = 'purchase.order.merged.line'
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Merged Lines'
    _table = 'purchase_order_merged_line'

    _columns = {
        'order_line_ids': fields.one2many('purchase.order.line', 'merged_id', string='Purchase Lines')
    }

    def create(self, cr, uid, vals, context={}):
        '''
        Set the line number to 0
        '''
        if self._name == 'purchase.order.merged.line':
            vals.update({'line_number': 0})
        return super(purchase_order_merged_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context={}):
        '''
        Update unit price of PO lines attached to the merged line
        '''
        new_context = context.copy()
        new_context.update({'update_merge': True})
        if 'price_unit' in vals:
            for merged_line in self.browse(cr, uid, ids, context=context):
                for po_line in merged_line.order_line_ids:
                    self.pool.get('purchase.order.line').write(cr, uid, [po_line.id], {'price_unit': vals['price_unit']}, context=new_context)

        return super(purchase_order_merged_line, self).write(cr, uid, ids, vals, context=context)

    def _update(self, cr, uid, id, product_qty, price=0.00, context={}, no_update=False):
        '''
        Update the quantity and the unit price according to the new qty
        '''
        line = self.browse(cr, uid, id, context=context)

        # If no PO line attached to this merged line, remove the merged line
        if not line.order_line_ids:
            self.unlink(cr, uid, [id], context=context)
            return False

        new_qty = line.product_qty + product_qty
        # Get the price according to the total qty
        new_price = self.pool.get('product.pricelist').price_get(cr, uid, 
                                                          [line.order_id.pricelist_id.id],
                                                          line.product_id.id,
                                                          new_qty,
                                                          line.order_id.partner_id.id,
                                                          {'uom': line.product_uom.id,
                                                           'date': line.order_id.date_order})[line.order_id.pricelist_id.id]
        values = {'product_qty': new_qty}
        if new_price:
            values.update({'price_unit': new_price})
        else:
            values.update({'price_unit': price})
            new_price = price

        if not no_update:
            self.write(cr, uid, [id], values, context=context)

        return id, new_price or False


purchase_order_merged_line()


class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    def link_merged_line(self, cr, uid, vals, product_id, order_id, product_qty, uom_id, price_unit=0.00, context={}):
        '''
        Check if a merged line exist. If not, create a new one and attach them to the Po line
        '''
        line_obj = self.pool.get('purchase.order.merged.line')
        domain = [('product_id', '=', product_id), ('order_id', '=', order_id), ('product_uom', '=', uom_id)]
        new_vals = vals.copy()

        # Search if a merged line already exist for the same product, the same order and the same UoM
        merged_ids = line_obj.search(cr, uid, domain, context=context)

        if not merged_ids:
            new_vals['order_id'] = order_id
            vals['merged_id'] = line_obj.create(cr, uid, new_vals, context=context)
        else:
            res_merged = line_obj._update(cr, uid, merged_ids[0], product_qty, price_unit, context=context, no_update=False)
            vals['merged_id'] = res_merged[0]
            vals['price_unit'] = res_merged[1]

        return vals

    def _update_merged_line(self, cr, uid, line_id, vals, context={}):
        '''
        Update the merged line
        '''
        merged_line_obj = self.pool.get('purchase.order.merged.line')

        # If it's an update of a line
        if vals and line_id:
            line = self.browse(cr, uid, line_id, context=context)
            # If the user has changed the product on the PO line
            if ('product_id' in vals and line.product_id.id != vals['product_id']) or ('product_uom' in vals and line.product_uom.id != vals['product_uom']):
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                self.write(cr, uid, line_id, {'merged_id': False}, context=context)
                res_merged = merged_line_obj._update(cr, uid, line.merged_id.id, -line.product_qty, line.price_unit, context=context)
                if res_merged and res_merged[1]:
                    vals.update({'price_unit': res_merged[1]})
                # Create or update an existing merged line with the new product
                vals = self.link_merged_line(cr, uid, vals, vals['product_id'], line.order_id.id, vals.get('product_qty', line.product_qty), vals.get('product_uom', line.product_uom.id), vals.get('price_unit', line.price_unit), context=context)
            if 'product_qty' in vals and line.product_qty != vals['product_qty']:
                res_merged = merged_line_obj._update(cr, uid, line.merged_id.id, vals['product_qty']-line.product_qty, line.price_unit, context=context)
                if res_merged and res_merged[1]:
                    vals.update({'price_unit': res_merged[1]})
            if 'price_unit' in vals and line.price_unit != vals['price_unit'] and not ('product_id' in vals and line.product_id.id != vals['product_id']):
                res_merged = merged_line_obj._update(cr, uid, line.merged_id.id, 0.00, vals['price_unit'], context=context)
                if res_merged and res_merged[1]:
                    vals.update({'price_unit': res_merged[1]})
                
                
        # If it's a new line
        elif not line_id:
            vals = self.link_merged_line(cr, uid, vals, vals['product_id'], vals['order_id'], vals['product_qty'], vals['product_uom'], vals['price_unit'], context=context)
        # If the line is removed
        elif not vals:
            line = self.browse(cr, uid, line_id, context=context)
            # Remove the qty from the merged line
            if line.merged_id:
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                self.write(cr, uid, [line.id], {'merged_id': False}, context=context)
                res_merged = merged_line_obj._update(cr, uid, line.merged_id.id, -line.product_qty, line.price_unit, context=context)

        return vals

    def create(self, cr, uid, vals, context={}):
        '''
        Create or update a merged line
        '''
        if not context:
            context = {}

        vals = self._update_merged_line(cr, uid, False, vals, context=context)

        return super(purchase_order_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context={}):
        '''
        Update merged line
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'product_id' in vals or 'product_qty' in vals or 'product_uom' in vals or 'price_unit' in vals and not context.get('update_merge'):
            for line_id in ids:
                vals = self._update_merged_line(cr, uid, line_id, vals, context=context)

        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context={}):
        '''
        Update the merged line
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for line_id in ids:
            self._update_merged_line(cr, uid, line_id, False, context=context)

        return super(purchase_order_line, self).unlink(cr, uid, ids, context=context)


    _columns = {
        'parent_line_id': fields.many2one('purchase.order.line', string='Parent line'),
        'merged_id': fields.many2one('purchase.order.merged.line', string='Merged line'),
        'origin': fields.char(size=64, string='Origin'),
    }

    def price_unit_change(self, cr, uid, ids, product_id, product_uom, product_qty, pricelist, partner_id, date_order, context={}):
        '''
        Display a warning message on change price unit if there are other lines with the same product and the same uom
        '''
        res = {}

        if not product_id or not product_uom or not product_qty:
            return res


        price = self.pool.get('product.pricelist').price_get(cr,uid,[pricelist], product_id, product_qty, partner_id,
                                                                {'uom': product_uom, 'date': date_order})[pricelist]

        order_id = context.get('purchase_id', False)
        if not order_id:
            return res

        lines = self.search(cr, uid, [('order_id', '=', order_id), ('product_id', '=', product_id), ('product_uom', '=', product_uom)])
        if lines and (price is False or price == 0.00):
            warning = {
                'title': 'Other lines updated !',
                'message': 'Be careful ! If you validate the change of the unit price by clicking on \'Save\' button, other lines with the same product and the same UoM will be updated too !',}
            res.update({'warning': warning})

        return res


    def open_split_wizard(self, cr, uid, ids, context={}):
        '''
        Open the wizard to split the line
        '''
        if not context:
            context = {}
 
        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            data = {'purchase_line_id': line.id, 'original_qty': line.product_qty, 'old_line_qty': line.product_qty}
            wiz_id = self.pool.get('split.purchase.order.line.wizard').create(cr, uid, data, context=context)
            return {'type': 'ir.actions.act_window',
                    'res_model': 'split.purchase.order.line.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wiz_id,
                    'context': context}


purchase_order_line()

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'
    
    _columns = {
        'purchase_list': fields.boolean(string='Purchase List ?', help='Check this box if the invoice comes from a purchase list', readonly=True, states={'draft':[('readonly',False)]}),
    }
    
account_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
