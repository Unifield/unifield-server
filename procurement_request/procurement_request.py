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

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from osv import osv, fields
from tools.translate import _
import decimal_precision as dp
import netsvc

from sale_override import SALE_ORDER_STATE_SELECTION
from msf_order_date.order_dates import compute_rts

class procurement_request(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Override the method to return 0.0 if the sale.order is a prcourement request
        '''
        res = {}
        new_ids = []
        
        for order in self.browse(cr, uid, ids, context=context):
            if order.procurement_request:
                res[order.id] = {}
                res[order.id]['amount_tax'] = 0.0
                res[order.id]['amount_total'] = 0.0
                res[order.id]['amount_untaxed'] = 0.0
            else:
                new_ids.append(order.id)
                
        res.update(super(procurement_request, self)._amount_all(cr, uid, new_ids, field_name, arg, context=context))
        
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Returns the procurement request search view instead of default sale order search view
        '''
        if not context:
            context = {}
        if view_type == 'search' and context.get('procurement_request') and not view_id:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_search_view')[1]

        return super(procurement_request, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
    
    #@@@ override sale.sale.order._get_order
    # Not modified method, but simply add here to fix an error on amount_total field
    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('sale.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()
    #@@@end override
    
    _columns = {
        'location_requestor_id': fields.many2one('stock.location', string='Location Requestor', ondelete="cascade",
        domain=[('usage', '=', 'internal')], help='You can only select an internal location'),
        'requestor': fields.char(size=128, string='Requestor', states={'draft': [('readonly', False)]}, readonly=True),
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', states={'draft': [('readonly', False)]}, readonly=True),
        'origin': fields.char(size=64, string='Origin', states={'draft': [('readonly', False)]}, readonly=True),
        'notes': fields.text(string='Notes'),
        'order_ids': fields.many2many('purchase.order', 'procurement_request_order_rel',
                                      'request_id', 'order_id', string='Orders', readonly=True),
        
        'amount_untaxed': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Untaxed Amount',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c=None: ids, ['order_line'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The amount without tax."),
        'amount_tax': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c=None: ids, ['order_line'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The tax amount."),
        'amount_total': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c=None: ids, ['order_line'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The total amount."),
        'state': fields.selection(SALE_ORDER_STATE_SELECTION, 'Order State', readonly=True, help="Gives the state of the quotation or sales order. \nThe exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception). \nThe 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to run on the date 'Ordered Date'.", select=True),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context: not context.get('procurement_request', False) and obj.pool.get('ir.sequence').get(cr, uid, 'sale.order') or obj.pool.get('ir.sequence').get(cr, uid, 'procurement.request'),
        'procurement_request': lambda obj, cr, uid, context: context.get('procurement_request', False),
        'state': 'draft',
        'warehouse_id': lambda obj, cr, uid, context: len(obj.pool.get('stock.warehouse').search(cr, uid, [])) and obj.pool.get('stock.warehouse').search(cr, uid, [])[0],
    }

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        if context.get('procurement_request') or vals.get('procurement_request', False):
            # Get the ISR number
            if not vals.get('name', False):
                vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'procurement.request')})

            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            if company.partner_id.address:
                address_id = company.partner_id.address[0].id
            else:
                address_id = self.pool.get('res.partner.address').search(cr, uid, [], limit=1)[0]
            vals['partner_id'] = company.partner_id.id
            vals['partner_order_id'] = address_id
            vals['partner_invoice_id'] = address_id
            vals['partner_shipping_id'] = address_id
            pl = self.pool.get('product.pricelist').search(cr, uid, [], limit=1)[0]
            vals['pricelist_id'] = pl
            if 'delivery_requested_date' in vals:
                vals['ready_to_ship_date'] = compute_rts(self, cr, uid, vals['delivery_requested_date'], 0, 'so', context=context)

        return super(procurement_request, self).create(cr, uid, vals, context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update date_planned of lines
        '''
        for req in self.browse(cr, uid, ids, context=context):
            # Only in case of Internal request
            if req.procurement_request and 'delivery_requested_date' in vals:
                rts = compute_rts(self, cr, uid, vals['delivery_requested_date'], 0, 'so', context=context)
                vals['ready_to_ship_date'] = rts
                for line in req.order_line:
                    self.pool.get('sale.order.line').write(cr, uid, line.id, {'date_planned': vals['delivery_requested_date']}, context=context)
        
        return super(procurement_request, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        Changes the state of the order to allow the deletion
        '''
        line_obj = self.pool.get('sale.order.line')
        
        del_ids = []
        normal_ids = []
        
        for request in self.browse(cr, uid, ids, context=context):
            if request.procurement_request and request.state in ['draft', 'cancel']:
                del_ids.append(request.id)
            elif not request.procurement_request:
                normal_ids.append(request.id)
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Internal Request(s) which are already validated !'))
                
        if del_ids:
            osv.osv.unlink(self, cr, uid, del_ids, context=context)
                
        return super(procurement_request, self).unlink(cr, uid, normal_ids, context=context)
    
    def search(self, cr, uid, args=None, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Adds automatically a domain to search only True sale orders if no procurement_request in context
        '''
        test = True
        if args is None:
            args = []
        if context is None:
            context = {}
        for a in args:
            if a[0] == 'procurement_request':
                test = False
        
        if not context.get('procurement_request', False) and test:
            args.append(('procurement_request', '=', False))
            
        return super(procurement_request, self).search(cr, uid, args, offset, limit, order, context, count)
   
    def _hook_copy_default(self, cr, uid, *args, **kwargs):
        id = kwargs['id']
        default = kwargs['default']
        context = kwargs['context']

        if not default:
            default = {}
            
        seq_obj = self.pool.get('ir.sequence')
        order = self.browse(cr, uid, id)

        name = (order.procurement_request or context.get('procurement_request', False)) and seq_obj.get(cr, uid, 'procurement.request') or seq_obj.get(cr, uid, 'sale.order')
        proc = order.procurement_request or context.get('procurement_request', False)
            
        default.update({
            'shipped': False,
            'invoice_ids': [],
            'picking_ids': [],
            'date_confirm': False,
            'procurement_request': proc,
        })

        if not 'name' in default:
            default.update({'name': name})

        return default
        
    def copy(self, cr, uid, id, default, context=None):
        # bypass name sequence
        new_id = super(procurement_request, self).copy(cr, uid, id, default, context=context)
        if new_id:
            new_order = self.read(cr, uid, new_id, ['delivery_requested_date', 'order_line'])
            if new_order['delivery_requested_date'] and new_order['order_line']:
                self.pool.get('sale.order.line').write(cr, uid, new_order['order_line'], {'date_planned': new_order['delivery_requested_date']})
        return new_id


    def wkf_action_cancel(self, cr, uid, ids, context=None):
        '''
        Cancel the procurement request and all lines
        '''
        line_ids = []
        for req in self.browse(cr, uid, ids, context=context):
            for line in req.order_line:
                if line.id not in line_ids:
                    line_ids.append(line.id)

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        self.pool.get('sale.order.line').write(cr, uid, line_ids, {'state': 'cancel'}, context=context)

        return True

    def validate_procurement(self, cr, uid, ids, context=None):
        '''
        Validate the request
        '''
        for req in self.browse(cr, uid, ids, context=context):
            if len(req.order_line) <= 0:
                raise osv.except_osv(_('Error'), _('You cannot validate an Internal request with no lines !'))
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        return True
    
    def confirm_procurement(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Confirmed the request
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        obj_data = self.pool.get('ir.model.data')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")

        self.write(cr, uid, ids, {'state': 'progress'}, context=context)

        for request in self.browse(cr, uid, ids, context=context):
            picking_id = False
            if not request.order_line:
                raise osv.except_osv(_('Error'), _('You cannot confirm an Internal request with no lines !'))
            else:
                message = _("The internal request '%s' has been confirmed.") %(request.name,)
                proc_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')
                context.update({'view_id': proc_view and proc_view[1] or False})
                self.log(cr, uid, request.id, message, context=context)
                
                # partly copy paste from action_ship_create
                for line in request.order_line:
                    #if line.type == 'make_to_order':
                    date_planned = datetime.now() + relativedelta(days=line.delay or 0.0)
                    date_planned = (date_planned - timedelta(days=company.security_lead)).strftime('%Y-%m-%d %H:%M:%S')
    
                    move_id = False
                    location_id = request.shop_id.warehouse_id.lot_stock_id.id
                    if not picking_id:
                        pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal')
                        picking_data = {'name': pick_name,
                                        'origin': request.name,
                                        'reason_type_id': obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_supply')[1],
                                        'type': 'internal',
                                        'state': 'draft',
                                        'move_type': request.picking_policy,
                                        'sale_id': request.id,
                                        'address_id': request.partner_shipping_id.id,
                                        'note': request.note,
                                        'invoice_state': (request.order_policy=='picking' and '2binvoiced') or 'none',
                                        'company_id': request.company_id.id,
                                        }
                        picking_id = self.pool.get('stock.picking').create(cr, uid, picking_data, context=context)
                    if line.product_id:
                        product_id = line.product_id.id
                        move_data = {'name': line.name[:64],
                                     'reason_type_id': obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_supply')[1],
                                     'picking_id': picking_id,
                                     'product_id': line.product_id.id,
                                     'date': date_planned,
                                     'date_expected': date_planned,
                                     'product_qty': line.product_uom_qty,
                                     'product_uom': line.product_uom.id,
                                     'product_uos_qty': line.product_uos_qty,
                                     'product_uos': (line.product_uos and line.product_uos.id)\
                                     or line.product_uom.id,
                                     'product_packaging': line.product_packaging.id,
                                     'address_id': line.address_allotment_id.id or request.partner_shipping_id.id,
                                     'location_id': obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1],
                                     'location_dest_id': request.location_requestor_id.id,
                                     'sale_line_id': line.id,
                                     'tracking_id': False,
                                     'state': 'draft', 
                                     'note': line.notes,
                                     'company_id': request.company_id.id,
                                     }
                        move_id = self.pool.get('stock.move').create(cr, uid, move_data, context=context)
                        # Confirm all moves
                        #move_obj.action_done(cr, uid, move_id, context=context)
                # Confirm the picking
                wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
    
                message = _("""The Internal moves '%s' is created according to the lines that have a product and the goods are moved.""") %(pick_name,)
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'view_picking_form')[1]
                self.pool.get('stock.picking').log(cr, uid, picking_id, message, context={'view_id': view_id})
        
                self.action_ship_create(cr, uid, ids, context=context, *args, **kwargs)
        
        return True
    
    def procurement_done(self, cr, uid, ids, context=None):
        '''
        Creates all procurement orders according to lines
        '''
        self.write(cr, uid, ids, {'state': 'done'})
        
        return True
    
    def pricelist_id_change(self, cr, uid, ids, pricelist_id):
        '''
        Display a warning message on pricelist change
        '''
        res = {}
        
        if pricelist_id and ids:
            order = self.browse(cr, uid, ids[0])
            if pricelist_id != order.pricelist_id.id and order.order_line:
                res.update({'warning': {'title': 'Currency change',
                                        'message': 'You have changed the currency of the order. \
                                         Please note that all order lines in the old currency will be changed to the new currency without conversion !'}})
                
        return res
    
procurement_request()

class procurement_request_line(osv.osv):
    _name = 'sale.order.line'
    _inherit= 'sale.order.line'
    
    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Override the method to return 0.0 if the line is a procurement request line
        '''
        res = {}
        new_ids= []
        for line in self.browse(cr, uid, ids):
            if line.order_id.procurement_request:
                res[line.id] = 0.0
            else:
                new_ids.append(line.id)
                
        res.update(super(procurement_request_line, self)._amount_line(cr, uid, new_ids, field_name, arg, context=context))
        
        return res
    
    def create(self, cr, uid, vals, context=None):
        '''
        Adds the date_planned value
        '''
        if context is None:
            context = {}

        if not 'date_planned' in vals and context.get('procurement_request'):
            if 'date_planned' in context:
                vals.update({'date_planned': context.get('date_planned')})
            else:
                date_planned = self.pool.get('sale.order').browse(cr, uid, vals.get('order_id'), context=context).delivery_requested_date
                vals.update({'date_planned': date_planned})
                
        return super(procurement_request_line, self).create(cr, uid, vals, context=context)
    
    def _get_fake_state(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['state']):
            ret[pol['id']] = pol['state']
        return ret
    
    _columns = {
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'latest': fields.char(size=64, string='Latest documents', readonly=True),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal', digits_compute= dp.get_precision('Sale Price')),
        'my_company_id': fields.many2one('res.company','Company',select=1),
        'supplier': fields.many2one('res.partner', 'Supplier', domain="[('id', '!=', my_company_id)]"),
        # openerp bug: eval invisible in p.o use the po line state and not the po state !
        'fake_state': fields.function(_get_fake_state, type='char', method=True, string='State', help='for internal use only'),
    }
    
    def _get_planned_date(self, cr, uid, c=None):
        if c is None:
            c = {}
        if 'procurement_request' in c:
            return c.get('date_planned', False)

        return super(procurement_request_line, self)._get_planned_date(cr, uid, c)

    _defaults = {
        'procurement_request': lambda self, cr, uid, c: c.get('procurement_request', False),
        'date_planned': _get_planned_date,
        'my_company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
    }
    
    def requested_product_id_change(self, cr, uid, ids, product_id, type, context=None):
        '''
        Fills automatically the product_uom_id field on the line when the 
        product was changed.
        '''
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')

        v = {}
        if not product_id:
            v.update({'product_uom': False, 'supplier': False, 'name': ''})
        else:
            product = product_obj.browse(cr, uid, product_id, context=context)
            v.update({'product_uom': product.uom_id.id, 'name': '[%s] %s'%(product.default_code, product.name)})
            if type != 'make_to_stock':
                v.update({'supplier': product.seller_ids and product.seller_ids[0].name.id})

        return {'value': v}
    
    def comment_change(self, cr, uid, ids, comment, product_id, type, context=None):
        '''
        Fill the level of nomenclatures with tag "to be defined" if you have only comment
        '''
        if context is None:
            context = {}
        res = {}
        obj_data = self.pool.get('ir.model.data')
        nomen_manda_0 =  obj_data.get_object_reference(cr, uid, 'procurement_request', 'nomen_tbd0')[1]
        nomen_manda_1 =  obj_data.get_object_reference(cr, uid, 'procurement_request', 'nomen_tbd1')[1]
        nomen_manda_2 =  obj_data.get_object_reference(cr, uid, 'procurement_request', 'nomen_tbd2')[1]
        nomen_manda_3 =  obj_data.get_object_reference(cr, uid, 'procurement_request', 'nomen_tbd3')[1]
        uom_tbd = obj_data.get_object_reference(cr, uid, 'procurement_request', 'uom_tbd')[1]
        
        if comment and not product_id:
            res.update({'nomen_manda_0': nomen_manda_0,
                        'nomen_manda_1': nomen_manda_1,
                        'nomen_manda_2': nomen_manda_2,
                        'nomen_manda_3': nomen_manda_3,
                        'product_uom': uom_tbd,
                        'name': 'To be defined',})
        return {'value': res}
    
procurement_request_line()

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'
    
    def _hook_action_picking_create_modify_out_source_loc_check(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_picking_create method from purchase>purchase.py>purchase_order class
        
        - allow to choose whether or not the source location of the corresponding outgoing stock move should
        match the destination location of incoming stock move
        '''
        order_line = kwargs['order_line']
        move_id = kwargs['move_id']
        proc_obj = self.pool.get('procurement.order')
        move_obj = self.pool.get('stock.move')
        sale_line_obj = self.pool.get('sale.order.line')
        if order_line.move_dest_id:
            proc_ids = proc_obj.search(cr, uid, [('move_id', '=', order_line.move_dest_id.id)], context=context)
            so_line_ids = sale_line_obj.search(cr, uid, [('procurement_id', 'in', proc_ids)], context=context)
            if all(not line.order_id or line.order_id.procurement_request for line in sale_line_obj.browse(cr, uid, so_line_ids, context=context)):
                for proc in proc_obj.browse(cr, uid, proc_ids, context=context):
                    if proc.move_id:
	                move_obj.write(cr, uid, [proc.move_id.id], {'state': 'draft'}, context=context)
        	        move_obj.unlink(cr, uid, [proc.move_id.id], context=context)
                    proc_obj.write(cr, uid, [proc.id], {'move_id': move_id}, context=context)
                    
        return super(purchase_order, self)._hook_action_picking_create_modify_out_source_loc_check(cr, uid, ids, context, *args, **kwargs)
    
purchase_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
