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
from tools.translate import _
import decimal_precision as dp

from sale_override import SALE_ORDER_STATE_SELECTION
from msf_order_date.order_dates import compute_rts

class procurement_request(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    def _ir_amount_all(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for ir in self.browse(cr, uid, ids, context=context):
            res[ir.id] = 0.0
            val = 0.0
            if ir.procurement_request:
                curr_browse = self.pool.get('res.users').browse(cr, uid, [uid], context)[0].company_id.currency_id
                for line in ir.order_line:
                    val += line.price_subtotal
                res[ir.id] = cur_obj.round(cr, uid, curr_browse, val)
        return res
    
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
        obj_data = self.pool.get('ir.model.data')
        if view_type == 'search' and context.get('procurement_request') and not view_id:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_search_view')[1]
            
        elif view_type == 'form' and context.get('procurement_request'):
            view_id = obj_data.get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')[1]

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
        domain=[('location_category', '!=', 'transition'), '|', ('usage', '=', 'internal'), '&', ('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')], help='You can only select an internal location'),
        'requestor': fields.char(size=128, string='Requestor', states={'draft': [('readonly', False)]}, readonly=True),
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', states={'draft': [('readonly', False)]}, readonly=True),
        'origin': fields.char(size=64, string='Origin', states={'draft': [('readonly', False)]}, readonly=True),
        'notes': fields.text(string='Notes'),
        'order_ids': fields.many2many('purchase.order', 'procurement_request_order_rel',
                                      'request_id', 'order_id', string='Orders', readonly=True),
        'ir_total_amount': fields.function(_ir_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Indicative Total Value'),
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
        'name': fields.char('Order Reference', size=64, required=True, readonly=True, select=True),
    }
    
    _defaults = {
        'name': lambda *a: False,
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
        elif not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'sale.order')})

        return super(procurement_request, self).create(cr, uid, vals, context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update date_planned of lines
        '''
        res = True
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

        proc = order.procurement_request or context.get('procurement_request', False)
            
        default.update({
            'shipped': False,
            'invoice_ids': [],
            'picking_ids': [],
            'date_confirm': False,
            'procurement_request': proc,
        })

        if not 'name' in default:
            name = (order.procurement_request or context.get('procurement_request', False)) and seq_obj.get(cr, uid, 'procurement.request') or seq_obj.get(cr, uid, 'sale.order')
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
        Validate the request (which is a the same object as a SO)
        It is the action called on the activity of the workflow.
        '''
        obj_data = self.pool.get('ir.model.data')
        nomen_manda_0 =  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1]
        nomen_manda_1 =  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1]
        nomen_manda_2 =  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1]
        nomen_manda_3 =  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd3')[1]
        uom_tbd = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
        nb_lines = 0
        for req in self.browse(cr, uid, ids, context=context):
            if len(req.order_line) <= 0:
                raise osv.except_osv(_('Error'), _('You cannot validate an Internal request with no lines !'))
            for line in req.order_line:
                if line.nomen_manda_0.id == nomen_manda_0 \
                or line.nomen_manda_1.id == nomen_manda_1 \
                or line.nomen_manda_2.id == nomen_manda_2 \
                or line.nomen_manda_3.id == nomen_manda_3 \
                or line.product_uom.id == uom_tbd:
                    nb_lines += 1
            if nb_lines:
                raise osv.except_osv(_('Error'), _('Please check the lines : you cannot have "To Be confirmed" for Nomenclature Level". You have %s lines to correct !')%nb_lines)
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        return True
    
    def confirm_procurement(self, cr, uid, ids, context=None):
        '''
        Confirmed the request
        '''
        if context is None:
            context = {}

        self.write(cr, uid, ids, {'state': 'progress'}, context=context)

        for request in self.browse(cr, uid, ids, context=context):
            if len(request.order_line) <= 0:
                raise osv.except_osv(_('Error'), _('You cannot confirm an Internal request with no lines !'))
            for line in request.order_line:
                # for FO
                if line.type == 'make_to_order' and not line.po_cft == 'cft':
                    if not line.supplier:
                        line_number = line.line_number
                        request_name = request.name
                        raise osv.except_osv(_('Error'), _('Please correct the line %s of the %s: the supplier is required for the procurement method "On Order" !')%(line_number,request_name))
                    # an Internal Request without product can only have Internal, Intersection or Intermission partners.
                    elif line.supplier and not line.product_id and line.order_id.procurement_request and line.supplier.partner_type not in ['internal', 'section', 'intermission']:
                        raise osv.except_osv(_('Warning'), _("""For an Internal Request with a procurement method 'On Order' and without product,
                        the supplier must be either in 'Internal', 'Inter-Section' or 'Intermission' type.
                        """))
            message = _("The internal request '%s' has been confirmed.") %(request.name,)
            proc_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')
            context.update({'view_id': proc_view and proc_view[1] or False})
            self.log(cr, uid, request.id, message, context=context)
        
        self.action_ship_create(cr, uid, ids, context=context)
        
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
        cur_obj = self.pool.get('res.currency')
        curr_browse = self.pool.get('res.users').browse(cr, uid, [uid], context)[0].company_id.currency_id
        for line in self.browse(cr, uid, ids):
            if line.order_id.procurement_request:
                subtotal = line.cost_price * line.product_uom_qty
                res[line.id] = cur_obj.round(cr, uid, curr_browse, subtotal)
            else:
                new_ids.append(line.id)
                
        res.update(super(procurement_request_line, self)._amount_line(cr, uid, new_ids, field_name, arg, context=context))
        
        return res
    
    def write(self, cr, uid, ids, vals, context):
        """
        Check if product or comment exist and set the the fields required accordingly.
        """
        if context is None:
            context = {}
        if vals.get('product_id', False):
            vals.update({'comment_ok': True})
        if vals.get('comment', False):
            vals.update({'product_ok': True})
        return super(procurement_request_line, self).write(cr, uid, ids, vals, context=context)
    
    def create(self, cr, uid, vals, context=None):
        '''
        Adds the date_planned value.
        Check if product or comment exist and set the the fields required accordingly.
        '''
        if context is None:
            context = {}
        if vals.get('product_id', False):
            vals.update({'comment_ok': True})
        if vals.get('comment', False):
            vals.update({'product_ok': True})

        if not 'date_planned' in vals and context.get('procurement_request'):
            if 'date_planned' in context:
                vals.update({'date_planned': context.get('date_planned')})
            else:
                date_planned = self.pool.get('sale.order').browse(cr, uid, vals.get('order_id'), context=context).delivery_requested_date
                vals.update({'date_planned': date_planned})

        # Compute the rounding of the product qty
        if vals.get('product_uom') and vals.get('product_uom_qty'):
            vals['product_uom_qty'] = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, vals.get('product_uom'), vals.get('product_uom_qty'), context=context)

        return super(procurement_request_line, self).create(cr, uid, vals, context=context)
       
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Compute the UoM qty according to UoM rounding value
        '''
        res = True
        for req in self.browse(cr, uid, ids, context=context):
            new_vals = vals.copy()
            # Compute the rounding of the product qty
            uom_id = new_vals.get('product_uom', req.product_uom.id)
            uom_qty = new_vals.get('product_uom_qty', req.product_uom_qty)
            new_vals['product_uom_qty'] = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, uom_id, uom_qty, context=context)
            res = res and super(procurement_request_line, self).write(cr, uid, [req.id], new_vals, context=context)

        return res
    
    def _get_fake_state(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['state']):
            ret[pol['id']] = pol['state']
        return ret
    
    def _get_product_id_ok(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for pol in self.read(cr, uid, ids, ['product_id']):
            if pol['product_id']:
                res[pol['id']] = True
            else:
                res[pol['id']] = False
        return res
    
    _columns = {
        'cost_price': fields.float(string='Cost price'),
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'latest': fields.char(size=64, string='Latest documents', readonly=True),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal', digits_compute= dp.get_precision('Sale Price')),
        'my_company_id': fields.many2one('res.company','Company',select=1),
        'supplier': fields.many2one('res.partner', 'Supplier', domain="[('id', '!=', my_company_id)]"),
        # openerp bug: eval invisible in p.o use the po line state and not the po state !
        'fake_state': fields.function(_get_fake_state, type='char', method=True, string='State', help='for internal use only'),
        'product_id_ok': fields.function(_get_product_id_ok, type="boolean", method=True, string='Product defined?', help='for if true the button "configurator" is hidden'),
        'product_ok': fields.boolean('Product selected'),
        'comment_ok': fields.boolean('Comment written'),
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
        'product_ok': False,
        'comment_ok': True,
    }
    

    def requested_product_id_change(self, cr, uid, ids, product_id, comment=False, context=None):
        '''
        Fills automatically the product_uom_id field and the name on the line when the 
        product is changed.
        Add a domain on the product_uom when a product is selected.
        '''
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

        value = {}
        domain = {}
        if not product_id:
            value = {'product_uom': False, 'supplier': False, 'name': '', 'type':'make_to_order', 'comment_ok': False, 'cost_price': False, 'price_subtotal': False}
            domain = {'product_uom':[], 'supplier': [('partner_type','in', ['internal', 'section', 'intermission'])]}
        elif product_id:
            product = product_obj.browse(cr, uid, product_id)
            value = {'product_uom': product.uom_id.id, 'name': '[%s] %s'%(product.default_code, product.name), 
                     'type': product.procure_method, 'comment_ok': True, 'cost_price': product.standard_price}
            if value['type'] != 'make_to_stock':
                value.update({'supplier': product.seller_ids and product.seller_ids[0].name.id})
            uom_val = uom_obj.read(cr, uid, [product.uom_id.id], ['category_id'])
            domain = {'product_uom':[('category_id','=',uom_val[0]['category_id'][0])]}
        return {'value': value, 'domain': domain}


    def requested_type_change(self, cr, uid, ids, product_id, type, context=None):
        """
        If there is a product, we check its type (procure_method) and update eventually the supplier.
        """
        if context is None:
            context = {}
        v = {}
        m = {}
        product_obj = self.pool.get('product.product')
        if product_id and type != 'make_to_stock':
            product = product_obj.browse(cr, uid, product_id, context=context)
            v.update({'supplier': product.seller_ids and product.seller_ids[0].name.id})
        elif product_id and type == 'make_to_stock':
            v.update({'supplier': False})
            product = product_obj.browse(cr, uid, product_id, context=context)
            if product.type in ('consu', 'service', 'service_recep'):
                v.update({'type': 'make_to_order'})
                m.update({'title': _('Warning'),
                          'message': _('You can\'t source a line \'from stock\' if line contains a non-stockable or service product.')})
        return {'value': v, 'warning': m}
    
    def comment_change(self, cr, uid, ids, comment, product_id, nomen_manda_0, context=None):
        '''
        Fill the level of nomenclatures with tag "to be defined" if you have only comment
        '''
        if context is None:
            context = {}
        value = {'comment': comment}
        domain = {}
        obj_data = self.pool.get('ir.model.data')
        tbd_0 =  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1]
        tbd_1 =  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1]
        tbd_2 =  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1]
        
        if comment and not product_id:
            value.update({'name': 'To be defined',
                          'supplier': False,
                          'product_ok': True})
            # it bugs with the To Be Defined => needs to be removed
#            if not nomen_manda_0:
#                value.update({'nomen_manda_0': tbd_0,
#                              'nomen_manda_1': tbd_1,
#                              'nomen_manda_2': tbd_2,})
            domain = {'product_uom':[], 'supplier': [('partner_type','in', ['internal', 'section', 'intermission'])]}
        if not comment:
            value.update({'product_ok': True})
            domain = {'product_uom':[], 'supplier': []}
        return {'value': value, 'domain': domain}
    
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
        po_line_obj = self.pool.get('purchase.order.line')
        # If the line comes from an ISR and it's not splitted line,
        # change the move_dest_id of this line (and their children)
        # to match with the procurement ordre move destination
        if order_line.move_dest_id and not order_line.parent_line_id:
            proc_ids = proc_obj.search(cr, uid, [('move_id', '=', order_line.move_dest_id.id)], context=context)
            so_line_ids = sale_line_obj.search(cr, uid, [('procurement_id', 'in', proc_ids)], context=context)
            po_line_ids = po_line_obj.search(cr, uid, [('move_dest_id', '=', order_line.move_dest_id.id)], context=context)
            if all(not line.order_id or line.order_id.procurement_request for line in sale_line_obj.browse(cr, uid, so_line_ids, context=context)):
                for proc in proc_obj.browse(cr, uid, proc_ids, context=context):
                    if proc.move_id:
                        move_obj.write(cr, uid, [proc.move_id.id], {'state': 'draft'}, context=context)
                        move_obj.unlink(cr, uid, [proc.move_id.id], context=context)
                    proc_obj.write(cr, uid, [proc.id], {'move_id': move_id}, context=context)
                    # Update the move_dest_id of all children to avoid the system to deal with a deleted stock move
                    po_line_obj.write(cr, uid, po_line_ids, {'move_dest_id': move_id}, context=context)
                    
        return super(purchase_order, self)._hook_action_picking_create_modify_out_source_loc_check(cr, uid, ids, context, *args, **kwargs)
    
purchase_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
