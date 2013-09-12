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

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from operator import itemgetter
from itertools import groupby

from osv import fields, osv
from tools.translate import _
import netsvc
import tools
import decimal_precision as dp
import logging
from os import path

from msf_partner import PARTNER_TYPE

#----------------------------------------------------------
# Procurement Order
#----------------------------------------------------------
class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def create(self, cr, uid, vals, context=None):
        '''
        create method for filling flag from yml tests
        '''
        if context is None:
            context = {}
        if context.get('update_mode') in ['init', 'update'] and 'from_yml_test' not in vals:
            logging.getLogger('init').info('PRO: set from yml test to True')
            vals['from_yml_test'] = True
        return super(procurement_order, self).create(cr, uid, vals, context=context)

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirms procurement and writes exception message if any.
        @return: True
        """
        move_obj = self.pool.get('stock.move')
        for procurement in self.browse(cr, uid, ids, context=context):
            if procurement.product_qty <= 0.00:
                raise osv.except_osv(_('Data Insufficient !'),
                    _('Please check the Quantity in Procurement Order(s), it should not be less than 1!'))
            if procurement.product_id.type in ('product', 'consu'):
                if not procurement.move_id:
                    source = procurement.location_id.id
                    reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
                    if procurement.procure_method == 'make_to_order':
                        reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
                        source = procurement.product_id.product_tmpl_id.property_stock_procurement.id
                    id = move_obj.create(cr, uid, {
                        'name': procurement.name,
                        'location_id': source,
                        'location_dest_id': procurement.location_id.id,
                        'product_id': procurement.product_id.id,
                        'product_qty': procurement.product_qty,
                        'product_uom': procurement.product_uom.id,
                        'date_expected': procurement.date_planned,
                        'state': 'draft',
                        'company_id': procurement.company_id.id,
                        'auto_validate': True,
                        'reason_type_id': reason_type_id,
                    })
                    move_obj.action_confirm(cr, uid, [id], context=context)
                    self.write(cr, uid, [procurement.id], {'move_id': id, 'close_move': 1})
        self.write(cr, uid, ids, {'state': 'confirmed', 'message': ''})
        return True
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset link to purchase order from update of on order purchase order
        '''
        if not default:
            default = {}
        default.update({'so_back_update_dest_po_id_procurement_order': False,
                        'so_back_update_dest_pol_id_procurement_order': False})
        return super(procurement_order, self).copy_data(cr, uid, id, default, context=context)
    
    _columns = {'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
                # this field is used when the po is modified during on order process, and the so must be modified accordingly
                # the resulting new purchase order line will be merged in specified po_id 
                'so_back_update_dest_po_id_procurement_order': fields.many2one('purchase.order', string='Destination of new purchase order line', readonly=True),
                'so_back_update_dest_pol_id_procurement_order': fields.many2one('purchase.order.line', string='Original purchase order line', readonly=True),
                }
    
    _defaults = {'from_yml_test': lambda *a: False,
                 }
    
procurement_order()


#----------------------------------------------------------
# Stock Picking
#----------------------------------------------------------
class stock_picking(osv.osv):
    _inherit = "stock.picking"
    _description = "Picking List"
    
    def _hook_state_list(self, cr, uid, *args, **kwargs):
        '''
        Change terms into states list
        '''
        state_list = kwargs['state_list']
        
        state_list['done'] = _('is closed.')
        
        return state_list
    
    def _get_stock_picking_from_partner_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of res.partner objects for which values have changed
        
        return the list of ids of stock.picking objects which need to get their fields updated
        
        self is res.partner object
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        pick_obj = self.pool.get('stock.picking')
        result = pick_obj.search(cr, uid, [('partner_id2', 'in', ids)], context=context)
        return result
    
    def _vals_get_stock_ov(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f:False})
            if obj.partner_id2:
                result[obj.id].update({'partner_type_stock_picking': obj.partner_id2.partner_type})
            
        return result
    
    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for pick in self.browse(cr, uid, ids, context=context):
            res[pick.id] = False
            for line in pick.move_lines:
                if line.inactive_product:
                    res[pick.id] = True
                    break
        
        return res

    _columns = {
        'state': fields.selection([
            ('draft', 'Draft'),
            ('auto', 'Waiting'),
            ('confirmed', 'Confirmed'),
            ('assigned', 'Available'),
            ('done', 'Closed'),
            ('cancel', 'Cancelled'),
            ('import', 'Import in progress'),
            ], 'State', readonly=True, select=True,
            help="* Draft: not confirmed yet and will not be scheduled until confirmed\n"\
                 "* Confirmed: still waiting for the availability of products\n"\
                 "* Available: products reserved, simply waiting for confirmation.\n"\
                 "* Waiting: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n"\
                 "* Closed: has been processed, can't be modified or cancelled anymore\n"\
                 "* Cancelled: has been cancelled, can't be confirmed anymore"),
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'address_id': fields.many2one('res.partner.address', 'Delivery address', help="Address of partner", readonly=False, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, domain="[('partner_id', '=', partner_id)]"),
        'partner_id2': fields.many2one('res.partner', 'Partner', required=False),
        'from_wkf': fields.boolean('From wkf'),
        'update_version_from_in_stock_picking': fields.integer(string='Update version following IN processing'),
        'partner_type_stock_picking': fields.function(_vals_get_stock_ov, method=True, type='selection', selection=PARTNER_TYPE, string='Partner Type', multi='get_vals_stock_ov', readonly=True, select=True,
                                                      store= {'stock.picking': (lambda self, cr, uid, ids, c=None: ids, ['partner_id2'], 10),
                                                              'res.partner': (_get_stock_picking_from_partner_ids, ['partner_type'], 10),}),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False),
        'fake_type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),
        'move_lines': fields.one2many('stock.move', 'picking_id', 'Internal Moves', states={'done': [('readonly', True)], 'cancel': [('readonly', True)], 'import': [('readonly', True)]}),
        'state_before_import': fields.char(size=64, string='State before import', readonly=True),
    }
    
    _defaults = {'from_yml_test': lambda *a: False,
                 'from_wkf': lambda *a: False,
                 'update_version_from_in_stock_picking': 0,
                 'fake_type': 'in',
                 }

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the stock picking contains a line with an inactive products
        '''
        inactive_lines = self.pool.get('stock.move').search(cr, uid, [('product_id.active', '=', False),
                                                                      ('picking_id', 'in', ids),
                                                                      ('picking_id.state', 'not in', ['draft', 'cancel', 'done'])], context=context)
        
        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')
            p_plural = len(inactive_lines) == 1 and _('this inactive product') or _('those inactive products')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the %s containing %s (see red %s of the document)') % (plural, l_plural, p_plural, l_plural))
            return False
        return True
    
    _constraints = [
            (_check_active_product, "You cannot validate this document because it contains a line with an inactive product", ['order_line', 'state'])
    ]
    
    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check restriction on products
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('stock.move')
        res = True

        for picking in self.browse(cr, uid, ids, context=context):
            if picking.type == 'internal' and picking.state not in ('draft', 'done', 'cancel'):
                res = res and line_obj._check_restriction_line(cr, uid, [x.id for x in picking.move_lines], context=context)

        return res
    
    def create(self, cr, uid, vals, context=None):
        '''
        create method for filling flag from yml tests
        '''
        if context is None:
            context = {}

        if not context.get('active_id',False):
            vals['from_wkf'] = True
        # in case me make a copy of a stock.picking coming from a workflow
        if context.get('not_workflow', False):
            vals['from_wkf'] = False
    
        if context.get('update_mode') in ['init', 'update'] and 'from_yml_test' not in vals:
            logging.getLogger('init').info('PICKING: set from yml test to True')
            vals['from_yml_test'] = True
            
        if not vals.get('partner_id2') and vals.get('address_id'):
            addr = self.pool.get('res.partner.address').browse(cr, uid, vals.get('address_id'), context=context)
            vals['partner_id2'] = addr.partner_id and addr.partner_id.id or False
            
        if not vals.get('address_id') and vals.get('partner_id2'):
            addr = self.pool.get('res.partner').address_get(cr, uid, vals.get('partner_id2'), ['delivery', 'default'])
            if not addr.get('delivery'):
                vals['address_id'] = addr.get('default')
            else:
                vals['address_id'] = addr.get('delivery')

        res = super(stock_picking, self).create(cr, uid, vals, context=context)
                
        return res

    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the partner or the address according to the other
        '''
        if isinstance(ids,(int, long)):
            ids = [ids]
        
        if not vals.get('address_id') and vals.get('partner_id2'):
            for pick in self.browse(cr, uid, ids, context=context):
                if pick.partner_id.id != vals.get('partner_id2'):
                    addr = self.pool.get('res.partner').address_get(cr, uid, vals.get('partner_id2'), ['delivery', 'default'])
                    if not addr.get('delivery'):
                        vals['address_id'] = addr.get('default')
                    else:
                        vals['address_id'] = addr.get('delivery')
                        
        if not vals.get('partner_id2') and vals.get('address_id'):
            for pick in self.browse(cr, uid, ids, context=context):
                if pick.address_id.id != vals.get('address_id'):
                    addr = self.pool.get('res.partner.address').browse(cr, uid, vals.get('address_id'), context=context)
                    vals['partner_id2'] = addr.partner_id and addr.partner_id.id or False
        
        res = super(stock_picking, self).write(cr, uid, ids, vals, context=context)
        
        return res
    
    def on_change_partner(self, cr, uid, ids, partner_id, address_id, context=None):
        '''
        Change the delivery address when the partner change.
        '''
        v = {}
        d = {}
        
        if not partner_id:
            v.update({'address_id': False})
        else:
            d.update({'address_id': [('partner_id', '=', partner_id)]})
            

        if address_id:
            addr = self.pool.get('res.partner.address').browse(cr, uid, address_id, context=context)
        
        if not address_id or addr.partner_id.id != partner_id:
            addr = self.pool.get('res.partner').address_get(cr, uid, partner_id, ['delivery', 'default'])
            if not addr.get('delivery'):
                addr = addr.get('default')
            else:
                addr = addr.get('delivery')
                
            v.update({'address_id': addr})
            
        
        return {'value': v,
                'domain': d}

    def return_to_state(self, cr, uid, ids, context=None):
        '''
        Return to initial state if the picking is 'Import in progress'
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for pick in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [pick.id], {'state': pick.state_before_import}, context=context)

        return True
    
    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the picking to done
        '''
        move_ids = []

        if isinstance(ids, (int, long)):
            ids = [ids]

        for pick in self.browse(cr, uid, ids, context=context):
            for move in pick.move_lines:
                if move.state not in ('cancel', 'done'):
                    move_ids.append(move.id)

        #Set all stock moves to done
        self.pool.get('stock.move').set_manually_done(cr, uid, move_ids, all_doc=all_doc, context=context)

        return True
    
    def _do_partial_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking
        
        - allow to modify the defaults data for move creation and copy
        '''
        defaults = kwargs.get('defaults')
        assert defaults is not None, 'missing defaults'
        
        return defaults
    
    def _picking_done_cond(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking
        
        - allow to conditionally execute the picking processing to done
        '''
        return True
    
    def _custom_code(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>stock.py>stock_picking
        
        - allow to execute specific custom code before processing picking to done
        - no supposed to modify partial_datas
        '''
        return True

    # @@@override stock>stock.py>stock_picking>do_partial
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial picking and moves done.
        @param partial_datas : Dictionary containing details of partial picking
                          like partner_id, address_id, delivery_date,
                          delivery moves with product_id, product_qty, uom
        @return: Dictionary of values
        """
        if isinstance(ids,(int, long)):
            ids = [ids]
        
        if context is None:
            context = {}
        else:
            context = dict(context)
        res = {}
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")

        internal_loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage','=','internal'), ('cross_docking_location_ok', '=', False)])
        ctx_avg = context.copy()
        ctx_avg['location'] = internal_loc_ids
        for pick in self.browse(cr, uid, ids, context=context):
            new_picking = None
            complete, too_many, too_few , not_aval = [], [], [], []
            move_product_qty = {}
            prodlot_ids = {}
            product_avail = {}
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
                    continue
                elif move.state in ('confirmed'):
                    not_aval.append(move)
                    continue
                partial_data = partial_datas.get('move%s'%(move.id), {})
                #Commented in order to process the less number of stock moves from partial picking wizard
                #assert partial_data, _('Missing partial picking data for move #%s') % (move.id)
                product_qty = partial_data.get('product_qty') or 0.0
                move_product_qty[move.id] = product_qty
                product_uom = partial_data.get('product_uom') or False
                product_price = partial_data.get('product_price') or 0.0
                product_currency = partial_data.get('product_currency') or False
                prodlot_id = partial_data.get('prodlot_id') or False
                prodlot_ids[move.id] = prodlot_id
                if move.product_qty == product_qty:
                    complete.append(move)
                elif move.product_qty > product_qty:
                    too_few.append(move)
                else:
                    too_many.append(move)

                # Average price computation
                if (pick.type == 'in') and (move.product_id.cost_method == 'average') and not move.location_dest_id.cross_docking_location_ok:
                    product = product_obj.browse(cr, uid, move.product_id.id, context=ctx_avg)
                    move_currency_id = move.company_id.currency_id.id
                    context['currency_id'] = move_currency_id
                    qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)

                    if product.id in product_avail:
                        product_avail[product.id] += qty
                    else:
                        product_avail[product.id] = product.qty_available

                    if qty > 0:
                        new_price = currency_obj.compute(cr, uid, product_currency,
                                move_currency_id, product_price, round=False, context=context)
                        new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                                product.uom_id.id)
                        if product.qty_available <= 0:
                            new_std_price = new_price
                        else:
                            # Get the standard price
                            amount_unit = product.price_get('standard_price', context)[product.id]
                            new_std_price = ((amount_unit * product_avail[product.id])\
                                + (new_price * qty))/(product_avail[product.id] + qty)
                        # Write the field according to price type field
                        product_obj.write(cr, uid, [product.id], {'standard_price': new_std_price})

                        # Record the values that were chosen in the wizard, so they can be
                        # used for inventory valuation if real-time valuation is enabled.
                        move_obj.write(cr, uid, [move.id],
                                {'price_unit': product_price,
                                 'price_currency_id': product_currency})
            for move in not_aval:
                if not new_picking:
                    new_picking = self.copy(cr, uid, pick.id,
                            {
                                'name': sequence_obj.get(cr, uid, 'stock.picking.%s'%(pick.type)),
                                'move_lines' : [],
                                'state':'draft',
                            })

            for move in too_few:
                product_qty = move_product_qty[move.id]
                if not new_picking:
                    new_picking = self.copy(cr, uid, pick.id,
                            {
                                'name': sequence_obj.get(cr, uid, 'stock.picking.%s'%(pick.type)),
                                'move_lines' : [],
                                'state':'draft',
                            })
                if product_qty != 0:
                    defaults = {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty, #TODO: put correct uos_qty
                            'picking_id' : new_picking,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': move.price_unit,
                            'processed_stock_move': True,
                    }
                    prodlot_id = prodlot_ids[move.id]
                    if prodlot_id:
                        defaults.update(prodlot_id=prodlot_id)
                    # override : call to hook added
                    defaults = self._do_partial_hook(cr, uid, ids, context, move=move, partial_datas=partial_datas, defaults=defaults)
                    move_obj.copy(cr, uid, move.id, defaults)

                move_obj.write(cr, uid, [move.id],
                        {
                            'product_qty' : move.product_qty - product_qty,
                            'product_uos_qty':move.product_qty - product_qty, #TODO: put correct uos_qty
                            'processed_stock_move': True,
                        })

            if new_picking:
                move_obj.write(cr, uid, [c.id for c in complete], {'picking_id': new_picking})
            for move in complete:
                # override : refactoring
                defaults = {}
                prodlot_id = prodlot_ids.get(move.id)
                if prodlot_id:
                    defaults.update(prodlot_id=prodlot_id)
                defaults = self._do_partial_hook(cr, uid, ids, context, move=move, partial_datas=partial_datas, defaults=defaults)
                move_obj.write(cr, uid, [move.id], defaults)
                # override : end

            for move in too_many:
                product_qty = move_product_qty[move.id]
                defaults = {
                    'product_qty' : product_qty,
                    'product_uos_qty': product_qty, #TODO: put correct uos_qty
                }
                prodlot_id = prodlot_ids.get(move.id)
                if prodlot_ids.get(move.id):
                    defaults.update(prodlot_id=prodlot_id)
                if new_picking:
                    defaults.update(picking_id=new_picking)
                # override : call to hook added
                defaults = self._do_partial_hook(cr, uid, ids, context, move=move, partial_datas=partial_datas, defaults=defaults)
                move_obj.write(cr, uid, [move.id], defaults)

            # At first we confirm the new picking (if necessary)
            if new_picking:
                self.write(cr, uid, [pick.id], {'backorder_id': new_picking})
                # custom code execution
                self._custom_code(cr, uid, ids, context=context, partial_datas=partial_datas, concerned_picking=self.browse(cr, uid, new_picking, context=context))
                # we confirm the new picking after its name was possibly modified by custom code - so the link message (top message) is correct
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
                # Then we finish the good picking
                if self._picking_done_cond(cr, uid, ids, context=context, partial_datas=partial_datas):
                    self.action_move(cr, uid, [new_picking])
                    wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
                delivered_pack_id = new_picking
            else:
                # custom code execution
                self._custom_code(cr, uid, ids, context=context, partial_datas=partial_datas, concerned_picking=pick)
                if self._picking_done_cond(cr, uid, ids, context=context, partial_datas=partial_datas):
                    self.action_move(cr, uid, [pick.id])
                    wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                delivered_pack_id = pick.id

            delivered_pack = self.browse(cr, uid, delivered_pack_id, context=context)
            res[pick.id] = {'delivered_picking': delivered_pack.id or False}

        return res
    # @@@override end

    # @@@override stock>stock.py>stock_picking>_get_invoice_type
    def _get_invoice_type(self, pick):
        src_usage = dest_usage = None
        inv_type = None
        if pick.invoice_state == '2binvoiced':
            if pick.move_lines:
                src_usage = pick.move_lines[0].location_id.usage
                dest_usage = pick.move_lines[0].location_dest_id.usage
            if pick.type == 'out' and dest_usage == 'supplier':
                inv_type = 'in_refund'
            elif pick.type == 'out' and dest_usage == 'customer':
                inv_type = 'out_invoice'
            elif (pick.type == 'in' and src_usage == 'supplier') or (pick.type == 'internal'):
                inv_type = 'in_invoice'
            elif pick.type == 'in' and src_usage == 'customer':
                inv_type = 'out_refund'
            else:
                inv_type = 'out_invoice'
        return inv_type
    
    def _hook_get_move_ids(self, cr, uid, *args, **kwargs):
        move_obj = self.pool.get('stock.move')
        pick = kwargs['pick']
        move_ids = move_obj.search(cr, uid, [('picking_id', '=', pick.id), 
                                             ('state', 'in', ('waiting', 'confirmed'))], order='prodlot_id, product_qty desc')
        
        return move_ids

    def draft_force_assign(self, cr, uid, ids, context=None):
        '''
        Confirm all stock moves
        '''
        res = super(stock_picking, self).draft_force_assign(cr, uid, ids)

        move_obj = self.pool.get('stock.move')
        move_ids = move_obj.search(cr, uid, [('state', '=', 'draft'), ('picking_id', 'in', ids)], context=context)
        move_obj.action_confirm(cr, uid, move_ids, context=context)

        return res

    def is_invoice_needed(self, cr, uid, sp=None):
        """
        Check if invoice is needed. Cases where we do not need invoice:
        - OUT from scratch (without purchase_id and sale_id) AND stock picking type in internal, external or esc
        - OUT from FO AND stock picking type in internal, external or esc
        So all OUT that have internel, external or esc should return FALSE from this method.
        This means to only accept intermission and intersection invoicing on OUT with reason type "Deliver partner".
        """
        res = True
        if not sp:
            return res
        # Fetch some values
        try:
            rt_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        except ValueError:
            rt_id = False
        # type out and partner_type in internal, external or esc
        if sp.type == 'out' and not sp.purchase_id and not sp.sale_id and sp.partner_id.partner_type in ['external', 'internal', 'esc']:
            res = False
        if sp.type == 'out' and not sp.purchase_id and not sp.sale_id and rt_id and sp.partner_id.partner_type in ['intermission', 'section']:
            # Search all stock moves attached to this one. If one of them is deliver partner, then is_invoice_needed is ok
            res = False
            sm_ids = self.pool.get('stock.move').search(cr, uid, [('picking_id', '=', sp.id)])
            if sm_ids:
                for sm in self.pool.get('stock.move').browse(cr, uid, sm_ids):
                    if sm.reason_type_id.id == rt_id:
                        res = True
        # partner is itself (those that own the company)
        company_partner_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id
        if sp.partner_id.id == company_partner_id.id:
            res = False
        return res

    def action_done(self, cr, uid, ids, context=None):
        """
        Create automatically invoice or NOT (regarding some criteria in is_invoice_needed)
        """
        res = super(stock_picking, self).action_done(cr, uid, ids, context=context)
        if res:
            if isinstance(ids, (int, long)):
                ids = [ids]
            for sp in self.browse(cr, uid, ids):
                sp_type = False
                inv_type = self._get_invoice_type(sp)
                # Check if no invoice needed
                is_invoice_needed = self.is_invoice_needed(cr, uid, sp)
                if not is_invoice_needed:
                    continue
                # we do not create invoice for procurement_request (Internal Request)
                if not sp.sale_id.procurement_request and sp.subtype == 'standard':
                    if sp.type == 'in' or sp.type == 'internal':
                        if inv_type == 'out_refund':
                            sp_type = 'sale_refund'
                        else:
                            sp_type = 'purchase'
                    elif sp.type == 'out':
                        if inv_type == 'in_refund':
                            sp_type = 'purchase_refund'
                        else:
                            sp_type = 'sale'
                    # Journal type
                    journal_type = sp_type
                    # Disturb journal for invoice only on intermission partner type
                    if sp.partner_id.partner_type == 'intermission':
                        journal_type = 'intermission'
                    journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', journal_type),
                                                                                    ('is_current_instance', '=', True)])
                    if not journal_ids:
                        raise osv.except_osv(_('Warning'), _('No %s journal found!') % (journal_type,))
                    # Create invoice
                    self.action_invoice_create(cr, uid, [sp.id], journal_ids[0], False, inv_type, {})
        return res
    
    def _get_price_unit_invoice(self, cr, uid, move_line, type):
        '''
        Update the Unit price according to the UoM received and the UoM ordered
        '''
        res = super(stock_picking, self)._get_price_unit_invoice(cr, uid, move_line, type)
        if move_line.purchase_line_id:
            po_uom_id = move_line.purchase_line_id.product_uom.id
            move_uom_id = move_line.product_uom.id
            uom_ratio = self.pool.get('product.uom')._compute_price(cr, uid, move_uom_id, 1, po_uom_id)
            return res/uom_ratio
        
        return res

    def action_invoice_create(self, cr, uid, ids, journal_id=False, group=False, type='out_invoice', context=None):
        """
        Attach an intermission journal to the Intermission Voucher IN/OUT if partner type is intermission from the picking.
        Prepare intermission voucher IN/OUT
        Change invoice purchase_list field to TRUE if this picking come from a PO which is 'purchase_list'
        """
        if isinstance(ids,(int, long)):
            ids = [ids]

        if not context:
            context = {}
        res = super(stock_picking, self).action_invoice_create(cr, uid, ids, journal_id, group, type, context)
        intermission_journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'intermission'),
                                                                                     ('is_current_instance', '=', True)])
        company = self.pool.get('res.users').browse(cr, uid, uid, context).company_id
        intermission_default_account = company.intermission_default_counterpart
        for pick in self.browse(cr, uid, [x for x in res]):
            # Check if PO and PO is purchase_list
            if pick.purchase_id and pick.purchase_id.order_type and pick.purchase_id.order_type == 'purchase_list':
                inv_id = res[pick.id]
                self.pool.get('account.invoice').write(cr, uid, [inv_id], {'purchase_list': True})
            # Check intermission
            if pick.partner_id.partner_type == 'intermission':
                inv_id = res[pick.id]
                if not intermission_journal_ids:
                    raise osv.except_osv(_('Error'), _('No Intermission journal found!'))
                if not intermission_default_account or not intermission_default_account.id:
                    raise osv.except_osv(_('Error'), _('Please configure a default intermission account in Company configuration.'))
                self.pool.get('account.invoice').write(cr, uid, [inv_id], {'journal_id': intermission_journal_ids[0], 
                    'is_intermission': True, 'account_id': intermission_default_account.id,})
                # Change currency for this invoice
                company_currency = company.currency_id and company.currency_id.id or False
                if not company_currency:
                    raise osv.except_osv(_('Warning'), _('No company currency found!'))
                wiz_account_change = self.pool.get('account.change.currency').create(cr, uid, {'currency_id': company_currency}, context=context)
                self.pool.get('account.change.currency').change_currency(cr, uid, [wiz_account_change], context={'active_id': inv_id})
        return res

    def action_confirm(self, cr, uid, ids, context=None):
        """
            stock.picking: action confirm
            if INCOMING picking: confirm and check availability
        """
        super(stock_picking, self).action_confirm(cr, uid, ids, context=context)
        move_obj = self.pool.get('stock.move')

        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.browse(cr, uid, ids):
            if pick.move_lines and pick.type == 'in':
                not_assigned_move = [x.id for x in pick.move_lines if x.state == 'confirmed']
                if not_assigned_move:
                    move_obj.action_assign(cr, uid, not_assigned_move)
        return True

    def _hook_action_assign_batch(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_assign method from stock>stock.py>stock_picking class
        
        -  when product is Expiry date mandatory, we "pre-assign" batch numbers regarding the available quantity
        and location logic in addition to FEFO logic (First expired first out).
        '''
        if isinstance(ids,(int, long)):
            ids = [ids]
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        if not context.get('already_checked'):
            for pick in self.browse(cr, uid, ids, context=context):
                # perishable for perishable or batch management
                move_obj.fefo_update(cr, uid, [move.id for move in pick.move_lines if move.product_id.perishable], context) # FEFO
        context['already_checked'] = True
        return super(stock_picking, self)._hook_action_assign_batch(cr, uid, ids, context=context)

    def change_all_location(self, cr, uid, ids, context=None):
        '''
        Launch the wizard to change all destination location of stock moves
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return {'type': 'ir.actions.act_window',
                'res_model': 'change.dest.location',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': self.pool.get('change.dest.location').create(cr, uid, {'picking_id': ids[0]}, context=context),
                'context': context,
                'target': 'new'}

stock_picking()

# ----------------------------------------------------
# Move
# ----------------------------------------------------

#
# Fields:
#   location_dest_id is only used for predicting futur stocks
#
class stock_move(osv.osv):

    _inherit = "stock.move"
    _description = "Stock Move with hook"

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the stock move to manually done
        '''
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def _get_from_dpo(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the move has a dpo_id
        '''
        res = {}
        if isinstance(ids,(int, long)):
            ids = [ids]

        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = False
            if move.dpo_id:
                res[move.id] = True

        return res

    def _search_from_dpo(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the list of moves from or not from DPO
        '''
        for arg in args:
            if arg[0] == 'from_dpo' and arg[1] == '=':
                return [('dpo_id', '!=', False)]
            elif arg[0] == 'from_dpo' and arg[1] in ('!=', '<>'):
                return [('dpo_id', '=', False)]
        
        return []
    
    def _default_location_destination(self, cr, uid, context=None):
        if not context:
            context = {}
        if context.get('picking_type') == 'out':
            wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
            if wh_ids:
                return self.pool.get('stock.warehouse').browse(cr, uid, wh_ids[0]).lot_output_id.id
    
        return False
    
    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        if isinstance(ids,(int, long)):
            ids = [ids]
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.picking_id and line.picking_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {'inactive_product': True,
                                'inactive_error': _('The product in line is inactive !')}
                
        return res  

    _columns = {
        'price_unit': fields.float('Unit Price', digits_compute=dp.get_precision('Picking Price Computation'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Not Available'), ('assigned', 'Available'), ('done', 'Closed'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True,
              help='When the stock move is created it is in the \'Draft\' state.\n After that, it is set to \'Not Available\' state if the scheduler did not find the products.\n When products are reserved it is set to \'Available\'.\n When the picking is done the state is \'Closed\'.\
              \nThe state is \'Waiting\' if the move is waiting for another one.'),
        'address_id': fields.many2one('res.partner.address', 'Delivery address', help="Address of partner", readonly=False, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, domain="[('partner_id', '=', partner_id)]"),
        'partner_id2': fields.many2one('res.partner', 'Partner', required=False),
        'already_confirmed': fields.boolean(string='Already confirmed'),
        'dpo_id': fields.many2one('purchase.order', string='Direct PO', help='PO from where this stock move is sourced.'),
        'from_dpo': fields.function(_get_from_dpo, fnct_search=_search_from_dpo, type='boolean', method=True, store=False, string='From DPO ?'),
        'from_wkf_line': fields.related('picking_id', 'from_wkf', type='boolean', string='Internal use: from wkf'),
        'fake_state': fields.related('state', type='char', store=False, string="Internal use"),
        'processed_stock_move': fields.boolean(string='Processed Stock Move'),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Error', store=False, multi='inactive'),
        'to_correct_ok': fields.boolean(string='Line to correct'),
        'text_error': fields.text(string='Error', readonly=True),
        'inventory_ids': fields.many2many('stock.inventory', 'stock_inventory_move_rel', 'move_id', 'inventory_id', 'Created Moves'),
    }

    _defaults = {
        'location_dest_id': _default_location_destination,
        'processed_stock_move': False, # to know if the stock move has already been partially or completely processed
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def _uom_constraint(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            if not self.pool.get('uom.tools').check_uom(cr, uid, obj.product_id.id, obj.product_uom.id, context):
                raise osv.except_osv(_('Error'), _('You have to select a product UOM in the same category than the purchase UOM of the product !'))

        return True
    
    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is restriction on lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context:
            context = {}

        for move in self.browse(cr, uid, ids, context=context):
            if move.picking_id and move.picking_id.type == 'internal' and move.product_id:
                if not self.pool.get('product.product')._get_restriction_error(cr, uid, move.product_id.id, vals={'constraints': {'location_id': move.location_dest_id}}, context=context):
                    return False

        return True

    _constraints = [(_uom_constraint, 'Constraint error on Uom', [])]

    def create(self, cr, uid, vals, context=None):
        '''
        Update the partner or the address according to the other
        '''
        if not vals.get('partner_id2') and vals.get('address_id'):
            addr = self.pool.get('res.partner.address').browse(cr, uid, vals.get('address_id'), context=context)
            vals['partner_id2'] = addr.partner_id and addr.partner_id.id or False
        elif not vals.get('partner_id2'):
            vals['partner_id2'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
            
        if not vals.get('address_id') and vals.get('partner_id2'):
            addr = self.pool.get('res.partner').address_get(cr, uid, vals.get('partner_id2'), ['delivery', 'default'])
            if not addr.get('delivery'):
                vals['address_id'] = addr.get('default')
            else:
                vals['address_id'] = addr.get('delivery')

        type = vals.get('type')
        if not type and vals.get('picking_id'):
            type = self.pool.get('stock.picking').browse(cr, uid, vals.get('picking_id'), context=context).type
            
        if type == 'in' and not vals.get('date_expected'):
            vals['date_expected'] = time.strftime('%Y-%m-%d %H:%M:%S')

        if vals.get('date_expected'):
            vals['date'] = vals.get('date_expected')
        
        res = super(stock_move, self).create(cr, uid, vals, context=context)
        
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the partner or the address according to the other
        '''
        
        if isinstance(ids, (int, long)):
            ids = [ids]        
        
        if not vals.get('address_id') and vals.get('partner_id2'):
            for move in self.browse(cr, uid, ids, context=context):
                if move.partner_id.id != vals.get('partner_id'):
                    addr = self.pool.get('res.partner').address_get(cr, uid, vals.get('partner_id2'), ['delivery', 'default'])
                    if not addr.get('delivery'):
                        vals['address_id'] = addr.get('default')
                    else:
                        vals['address_id'] = addr.get('delivery')
                        
        if not vals.get('partner_id2') and vals.get('address_id'):
            for move in self.browse(cr, uid, ids, context=context):
                if move.address_id.id != vals.get('address_id'):
                    addr = self.pool.get('res.partner.address').browse(cr, uid, vals.get('address_id'), context=context)
                    vals['partner_id2'] = addr.partner_id and addr.partner_id.id or False

        if vals.get('date_expected'):
            for move in self.browse(cr, uid, ids, context=context):
                if vals.get('state', move.state) not in ('done', 'cancel'):
                    vals['date'] = vals.get('date_expected')
        
        res = super(stock_move, self).write(cr, uid, ids, vals, context=context)

        return res
    
    def on_change_partner(self, cr, uid, ids, partner_id, address_id, context=None):
        '''
        Change the delivery address when the partner change.
        '''
        v = {}
        d = {}
        
        if not partner_id:
            v.update({'address_id': False})
        else:
            d.update({'address_id': [('partner_id', '=', partner_id)]})
            

        if address_id:
            addr = self.pool.get('res.partner.address').browse(cr, uid, address_id, context=context)
        
        if not address_id or addr.partner_id.id != partner_id:
            addr = self.pool.get('res.partner').address_get(cr, uid, partner_id, ['delivery', 'default'])
            if not addr.get('delivery'):
                addr = addr.get('default')
            else:
                addr = addr.get('delivery')
                
            v.update({'address_id': addr})
            
        
        return {'value': v,
                'domain': d}
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        Remove the already confirmed flag
        '''
        if default is None:
            default = {}
        default.update({'already_confirmed':False})
        
        return super(stock_move, self).copy(cr, uid, id, default, context=context)
    
    def fefo_update(self, cr, uid, ids, context=None):
        """
        Update batch, Expiry Date, Location according to FEFO logic
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        loc_obj = self.pool.get('stock.location')
        prodlot_obj = self.pool.get('stock.production.lot')
        for move in self.browse(cr, uid, ids, context):
            # FEFO logic
            if move.state == 'assigned': # a check_availability has already been done in action_assign, so we take only the 'assigned' lines
                needed_qty = move.product_qty
                res = loc_obj.compute_availability(cr, uid, [move.location_id.id], True, move.product_id.id, move.product_uom.id, context=context)
                if 'fefo' in res:
                    # We need to have the value like below because we need to have the id of the m2o (which is not possible if we do self.read(cr, uid, move.id))
                    values = {'name': move.name,
                              'sale_line_id': move.sale_line_id and move.sale_line_id.id or False,
                              'picking_id': move.picking_id.id,
                              'product_uom': move.product_uom.id,
                              'product_id': move.product_id.id,
                              'date_expected': move.date_expected,
                              'date': move.date,
                              'state': 'assigned',
                              'location_dest_id': move.location_dest_id.id,
                              'reason_type_id': move.reason_type_id.id,
                              }
                    for loc in res['fefo']:
                        # if source == destination, the state becomes 'done', so we don't do fefo logic in that case
                        if not move.location_dest_id.id == loc['location_id']:
                            # we ignore the batch that are outdated
                            expired_date = prodlot_obj.read(cr, uid, loc['prodlot_id'], ['life_date'], context)['life_date']
                            if datetime.strptime(expired_date, "%Y-%m-%d") >= datetime.today():
                                # as long all needed are not fulfilled
                                if needed_qty:
                                    # if the batch already exists and qty is enough, it is available (assigned)
                                    if needed_qty <= loc['qty']:
                                        if move.prodlot_id.id == loc['prodlot_id']:
                                            self.write(cr, uid, move.id, {'state': 'assigned'}, context)
                                        else:
                                            self.write(cr, uid, move.id, {'product_qty': needed_qty, 'product_uom': loc['uom_id'], 
                                                                        'location_id': loc['location_id'], 'prodlot_id': loc['prodlot_id']}, context)
                                        needed_qty = 0.0
                                        break
                                    elif needed_qty:
                                        # we take all available
                                        selected_qty = loc['qty']
                                        needed_qty -= selected_qty
                                        dict_for_create = {}
                                        dict_for_create = values.copy()
                                        dict_for_create.update({'product_uom': loc['uom_id'], 'product_qty': selected_qty, 'location_id': loc['location_id'], 'prodlot_id': loc['prodlot_id']})
                                        self.create(cr, uid, dict_for_create, context)
                                        self.write(cr, uid, move.id, {'product_qty': needed_qty})
                    # if the batch is outdated, we remove it
                    if not context.get('yml_test', False):
                        if move.expired_date and not datetime.strptime(move.expired_date, "%Y-%m-%d") >= datetime.today():
                            self.write(cr, uid, move.id, {'prodlot_id': False}, context)
            elif move.state == 'confirmed':
                # we remove the prodlot_id in case that the move is not available
                self.write(cr, uid, move.id, {'prodlot_id': False}, context)
        return True
    
    def action_confirm(self, cr, uid, ids, context=None):
        '''
        Set the bool already confirmed to True
        '''
        res = super(stock_move, self).action_confirm(cr, uid, ids, context=context)
        
        self.write(cr, uid, ids, {'already_confirmed': True}, context=context)
        
        return res
    
    def _hook_confirmed_move(self, cr, uid, *args, **kwargs):
        '''
        Always return True
        '''
        move = kwargs['move']
        if not move.already_confirmed:
            self.action_confirm(cr, uid, [move.id])
        return True
    
    def _hook_move_cancel_state(self, cr, uid, *args, **kwargs):
        '''
        Change the state of the chained move
        '''
        if kwargs.get('context'):
            kwargs['context'].update({'call_unlink': True})
        return {'state': 'cancel'}, kwargs.get('context', {})

    def _hook_write_state_stock_move(self, cr, uid, done, notdone, count):
        if done:
            count += len(done)

            #If source location == dest location THEN stock move is done.
            for line in self.read(cr,uid,done,['location_id','location_dest_id']):
                if line.get('location_id') and line.get('location_dest_id') and line.get('location_id') == line.get('location_dest_id'):
                    self.write(cr, uid, [line['id']], {'state': 'done'})
                else:
                    self.write(cr, uid, [line['id']], {'state': 'assigned'})

        if notdone:
            self.write(cr, uid, notdone, {'state': 'confirmed'})
        return count
    
    def _hook_check_assign(self, cr, uid, *args, **kwargs):
        '''
        kwargs['move'] is the current move
        '''
        move = kwargs['move']
        return move.location_id.usage == 'supplier'

    def _hook_cancel_assign_batch(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the cancel_assign method from stock>stock.py>stock_move class
        
        -  it erases the batch number associated if any and reset the source location to the original one.
        '''
        if isinstance(ids,(int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context):
            if line.prodlot_id:
                self.write(cr, uid, ids, {'prodlot_id': False, 'expired_date': False})
            if line.location_id.location_id and line.location_id.location_id.usage != 'view':
                self.write(cr, uid, ids, {'location_id': line.location_id.location_id.id})
        return True

    def _hook_copy_stock_move(self, cr, uid, res, move, done, notdone):
        while res:
            r = res.pop(0)
            move_id = self.copy(cr, uid, move.id, {'line_number': move.line_number, 'product_qty': r[0],'product_uos_qty': r[0] * move.product_id.uos_coeff,'location_id': r[1]})
            if r[2]:
                done.append(move_id)
            else:
                notdone.append(move_id)
        return done, notdone 

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        defaults = kwargs.get('defaults')
        assert defaults is not None, 'missing defaults'
        
        return defaults


    # @@@override stock>stock.py>stock_move>do_partial
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial pickings and moves done.
        @param partial_datas: Dictionary containing details of partial picking
                          like partner_id, address_id, delivery_date, delivery
                          moves with product_id, product_qty, uom
        """
        
        if isinstance(ids,(int, long)):
            ids = [ids]
        
        res = {}
        picking_obj = self.pool.get('stock.picking')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        complete, too_many, too_few = [], [], []
        move_product_qty = {}
        prodlot_ids = {}
        internal_loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage','=','internal'), ('cross_docking_location_ok', '=', False)])
        ctx_avg = context.copy()
        ctx_avg['location'] = internal_loc_ids
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('done', 'cancel'):
                continue
            partial_data = partial_datas.get('move%s'%(move.id), False)
            assert partial_data, _('Missing partial picking data for move #%s') % (move.id)
            product_qty = partial_data.get('product_qty',0.0)
            move_product_qty[move.id] = product_qty
            product_uom = partial_data.get('product_uom',False)
            product_price = partial_data.get('product_price',0.0)
            product_currency = partial_data.get('product_currency',False)
            prodlot_ids[move.id] = partial_data.get('prodlot_id')
            if move.product_qty == product_qty:
                complete.append(move)
            elif move.product_qty > product_qty:
                too_few.append(move)
            else:
                too_many.append(move)

            # Average price computation
            if (move.picking_id.type == 'in') and (move.product_id.cost_method == 'average') and not move.location_dest_id.cross_docking_location_ok:
                product = product_obj.browse(cr, uid, move.product_id.id, context=ctx_avg)
                move_currency_id = move.company_id.currency_id.id
                context['currency_id'] = move_currency_id
                qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
                if qty > 0:
                    new_price = currency_obj.compute(cr, uid, product_currency,
                            move_currency_id, product_price, round=False, context=context)
                    new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                            product.uom_id.id)
                    if product.qty_available <= 0:
                        new_std_price = new_price
                    else:
                        # Get the standard price
                        amount_unit = product.price_get('standard_price', context)[product.id]
                        new_std_price = ((amount_unit * product.qty_available)\
                            + (new_price * qty))/(product.qty_available + qty)

                    product_obj.write(cr, uid, [product.id],{'standard_price': new_std_price})

                    # Record the values that were chosen in the wizard, so they can be
                    # used for inventory valuation if real-time valuation is enabled.
                    self.write(cr, uid, [move.id],
                                {'price_unit': product_price,
                                 'price_currency_id': product_currency,
                                })

        for move in too_few:
            product_qty = move_product_qty[move.id]
            if product_qty != 0:
                defaults = {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty,
                            'picking_id' : move.picking_id.id,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': move.price_unit,
                            }
                prodlot_id = prodlot_ids[move.id]
                if prodlot_id:
                    defaults.update(prodlot_id=prodlot_id)
                # override : call to hook added
                defaults = self._do_partial_hook(cr, uid, ids, context, move=move, partial_datas=partial_datas, defaults=defaults)
                new_move = self.copy(cr, uid, move.id, defaults)
                complete.append(self.browse(cr, uid, new_move))
            self.write(cr, uid, [move.id],
                    {
                        'product_qty' : move.product_qty - product_qty,
                        'product_uos_qty':move.product_qty - product_qty,
                    })


        for move in too_many:
            self.write(cr, uid, [move.id],
                    {
                        'product_qty': move.product_qty,
                        'product_uos_qty': move.product_qty,
                    })
            complete.append(move)

        for move in complete:
            # override : refactoring
            defaults = {}
            prodlot_id = prodlot_ids.get(move.id)
            if prodlot_id:
                defaults.update(prodlot_id=prodlot_id)
            defaults = self._do_partial_hook(cr, uid, ids, context, move=move, partial_datas=partial_datas, defaults=defaults)
            self.write(cr, uid, [move.id], defaults)
            # override : end
            self.action_done(cr, uid, [move.id], context=context)
            if  move.picking_id.id :
                # TOCHECK : Done picking if all moves are done
                cr.execute("""
                    SELECT move.id FROM stock_picking pick
                    RIGHT JOIN stock_move move ON move.picking_id = pick.id AND move.state = %s
                    WHERE pick.id = %s""",
                            ('done', move.picking_id.id))
                res = cr.fetchall()
                if len(res) == len(move.picking_id.move_lines):
                    picking_obj.action_move(cr, uid, [move.picking_id.id])
                    wf_service.trg_validate(uid, 'stock.picking', move.picking_id.id, 'button_done', cr)

        return [move.id for move in complete]
    # @@@override end

    def _get_destruction_products(self, cr, uid, ids, product_ids=False, context=None, recursive=False):
        """ Finds the product quantity and price for particular location.
        """
        if context is None:
            context = {}
        if isinstance(ids,(int, long)):
            ids = [ids]

        result = []
        for move in self.browse(cr, uid, ids, context=context):
            # add this move into the list of result
            dg_check_flag = ''
            if move.dg_check:
                dg_check_flag = 'x'
                
            np_check_flag = ''
            if move.np_check:
                np_check_flag = 'x'
            sub_total = move.product_qty * move.product_id.standard_price
            
            currency = ''
            if move.purchase_line_id and move.purchase_line_id.currency_id:
                currency = move.purchase_line_id.currency_id.name
            elif move.sale_line_id and move.sale_line_id.currency_id:
                currency = move.sale_line_id.currency_id.name
            
            result.append({
                'prod_name': move.product_id.name,
                'prod_code': move.product_id.code,
                'prod_price': move.product_id.standard_price,
                'sub_total': sub_total,
                'currency': currency,
                'origin': move.origin,
                'expired_date': move.expired_date,
                'prodlot_id': move.prodlot_id.name,
                'dg_check': dg_check_flag,
                'np_check': np_check_flag,
                'uom': move.product_uom.name,
                'prod_qty': move.product_qty,
            })
        return result

    def in_action_confirm(self, cr, uid, ids, context=None):
        """
            Incoming: draft or confirmed: validate and assign
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.action_confirm(cr, uid, ids, context)
        self.action_assign(cr, uid, ids, context)
        return True

stock_move()

#-----------------------------------------
#   Stock location
#-----------------------------------------
class stock_location(osv.osv):
    _name = 'stock.location'
    _inherit = 'stock.location'
    
    def init(self, cr):
        """
        Load data.xml asap
        """
        if hasattr(super(stock_location, self), 'init'):
            super(stock_location, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        logging.getLogger('init').info('HOOK: module stock_override: loading stock_data.xml')
        pathname = path.join('stock_override', 'stock_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'stock_override', file, {}, mode='init', noupdate=False)
    
    def _product_value(self, cr, uid, ids, field_names, arg, context=None):
        """Computes stock value (real and virtual) for a product, as well as stock qty (real and virtual).
        @param field_names: Name of field
        @return: Dictionary of values
        """
        result = super(stock_location, self)._product_value(cr, uid, ids, field_names, arg, context=context)
        
        product_product_obj = self.pool.get('product.product')
        currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        currency_obj = self.pool.get('res.currency')
        currency = currency_obj.browse(cr, uid, currency_id, context=context)
        if context.get('product_id'):
            view_ids = self.search(cr, uid, [('usage', '=', 'view')], context=context)
            result.update(dict([(i, {}.fromkeys(field_names, 0.0)) for i in list(set([aaa for aaa in view_ids]))]))
            for loc_id in view_ids:
                c = (context or {}).copy()
                c['location'] = loc_id
                c['compute_child'] = True
                for prod in product_product_obj.browse(cr, uid, [context.get('product_id')], context=c):
                    for f in field_names:
                        if f == 'stock_real':
                            if loc_id not in result:
                                result[loc_id] = {}
                            result[loc_id][f] += prod.qty_available
                        elif f == 'stock_virtual':
                            result[loc_id][f] += prod.virtual_available
                        elif f == 'stock_real_value':
                            amount = prod.qty_available * prod.standard_price
                            amount = currency_obj.round(cr, uid, currency, amount)
                            result[loc_id][f] += amount
                        elif f == 'stock_virtual_value':
                            amount = prod.virtual_available * prod.standard_price
                            amount = currency_obj.round(cr, uid, currency, amount)
                            result[loc_id][f] += amount
                            
        return result

    def _fake_get(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            result[id] = False
        return result

    def _prod_loc_search(self, cr, uid, ids, fields, arg, context=None):
        if not arg or not arg[0] or not arg[0][2] or not arg[0][2][0]:
            return []
        if context is None:
            context = {}
        id_nonstock = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        prod_obj = self.pool.get('product.product').browse(cr, uid, arg[0][2][0])
        if prod_obj and prod_obj.type == 'consu':
            if arg[0][2][1] == 'in':
                id_virt = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock','stock_location_locations_virtual')[1]
                ids_child = self.pool.get('stock.location').search(cr,uid,[('location_id', 'child_of', id_virt)])
                return [('id', 'in', [id_nonstock, id_cross]+ids_child)]
            else:
                return [('id', 'in', [id_cross])]

        elif prod_obj and  prod_obj.type != 'consu':
                if arg[0][2][1] == 'in':
                    return [('id', 'in', ids_child)]
                else:
                    return [('id', 'not in', [id_nonstock]), ('usage', '=', 'internal')]

        return [('id', 'in', [])]

    def _cd_search(self, cr, uid, ids, fields, arg, context=None):
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        if context is None:
            context = {}
        if arg[0][2]:
            obj_pol = arg[0][2][0] and self.pool.get('purchase.order.line').browse(cr, uid, arg[0][2][0]) or False
            if  (obj_pol and obj_pol.order_id.cross_docking_ok) or arg[0][2][1]:
                return [('id', 'in', [id_cross])]
        return []

    def _check_usage(self, cr, uid, ids, fields, arg, context=None):
        if not arg or not arg[0][2]:
            return []
        if context is None:
            context = {}
        prod_obj = self.pool.get('product.product').browse(cr, uid, arg[0][2])
        if prod_obj.type == 'service_recep':
            ids = self.pool.get('stock.location').search(cr, uid, [('usage','=', 'inventory')])
            return [('id', 'in', ids)]
        elif prod_obj.type == 'consu':
            return []
        else:
            ids = self.pool.get('stock.location').search(cr, uid, [('usage','=', 'internal')])
            return [('id', 'in', ids)]
        return []


    _columns = {
        'chained_location_type': fields.selection([('none', 'None'), ('customer', 'Customer'), ('fixed', 'Fixed Location'), ('nomenclature', 'Nomenclature')],
                                'Chained Location Type', required=True,
                                help="Determines whether this location is chained to another location, i.e. any incoming product in this location \n" \
                                     "should next go to the chained location. The chained location is determined according to the type :"\
                                     "\n* None: No chaining at all"\
                                     "\n* Customer: The chained location will be taken from the Customer Location field on the Partner form of the Partner that is specified in the Picking list of the incoming products." \
                                     "\n* Fixed Location: The chained location is taken from the next field: Chained Location if Fixed." \
                                     "\n* Nomenclature: The chained location is taken from the options field: Chained Location is according to the nomenclature level of product."\
                                    ),
        'chained_options_ids': fields.one2many('stock.location.chained.options', 'location_id', string='Chained options'),
        'optional_loc': fields.boolean(string='Is an optional location ?'),
        'stock_real': fields.function(_product_value, method=True, type='float', string='Real Stock', multi="stock"),
        'stock_virtual': fields.function(_product_value, method=True, type='float', string='Virtual Stock', multi="stock"),
        'stock_real_value': fields.function(_product_value, method=True, type='float', string='Real Stock Value', multi="stock", digits_compute=dp.get_precision('Account')),
        'stock_virtual_value': fields.function(_product_value, method=True, type='float', string='Virtual Stock Value', multi="stock", digits_compute=dp.get_precision('Account')),
        'check_prod_loc': fields.function(_fake_get, method=True, type='many2one', string='zz', fnct_search=_prod_loc_search),
        'check_cd': fields.function(_fake_get, method=True, type='many2one', string='zz', fnct_search=_cd_search),
        'check_usage': fields.function(_fake_get, method=True, type='many2one', string='zz', fnct_search=_check_usage),
        'virtual_location': fields.boolean(string='Virtual location'),

    }

    #####
    # Chained location on nomenclature level
    #####
    def _hook_chained_location_get(self, cr, uid, context=None, *args, **kwargs):
        '''
        Return the location according to nomenclature level
        '''
        location = kwargs['location']
        product = kwargs['product']
        result = kwargs['result']

        if location.chained_location_type == 'nomenclature':
            for opt in location.chained_options_ids:
                if opt.nomen_id.id == product.nomen_manda_0.id:
                    return opt.dest_location_id

        return result

    def _hook_proct_reserve(self, cr, uid, product_qty, result, amount, id, ids ):
        result.append((amount, id, True))
        product_qty -= amount
        if product_qty <= 0.0:
            return result
        else:
            result = []
            result.append((amount, id, True))
            if len(ids) >= 1:
                result.append((product_qty, ids[0], False))
            else:
                result.append((product_qty, id, False))
            return result
        return []

    def on_change_location_type(self, cr, uid, ids, chained_location_type, context=None):
        '''
        If the location type is changed to 'Nomenclature', set some other fields values
        '''
        if chained_location_type and chained_location_type == 'nomenclature':
            return {'value': {'chained_auto_packing': 'transparent',
                              'chained_picking_type': 'internal',
                              'chained_delay': 0}}

        return {}


stock_location()

class stock_location_chained_options(osv.osv):
    _name = 'stock.location.chained.options'
    _rec_name = 'location_id'
    
    _columns = {
        'dest_location_id': fields.many2one('stock.location', string='Destination Location', required=True),
        'nomen_id': fields.many2one('product.nomenclature', string='Nomenclature Level', required=True),
        'location_id': fields.many2one('stock.location', string='Location', required=True),
    }

stock_location_chained_options()


class ir_values(osv.osv):
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req)
        trans_obj = self.pool.get('ir.translation')
        new_values = values
        move_accepted_values = {'client_action_multi': [],
                                    'client_print_multi': [],
                                    'client_action_relate': ['act_relate_picking'],
                                    'tree_but_action': [],
                                    'tree_but_open': []}
        
        incoming_accepted_values = {'client_action_multi': ['act_stock_return_picking', 'action_stock_invoice_onshipping'],
                                    'client_print_multi': ['Reception'],
                                    'client_action_relate': ['View_log_stock.picking'],
                                    'tree_but_action': [],
                                    'tree_but_open': []}
        
        internal_accepted_values = {'client_action_multi': [],
                                    'client_print_multi': ['Labels', 'Internal Move Excel Export', 'Internal Move'],
                                    'client_action_relate': [],
                                    'tree_but_action': [],
                                    'tree_but_open': []}
        
        delivery_accepted_values = {'client_action_multi': [],
                                    'client_print_multi': ['Labels'],
                                    'client_action_relate': [''],
                                    'tree_but_action': [],
                                    'tree_but_open': []}
        
        picking_accepted_values = {'client_action_multi': [],
                                    'client_print_multi': ['Picking Ticket', 'Pre-Packing List', 'Labels'],
                                    'client_action_relate': [''],
                                    'tree_but_action': [],
                                    'tree_but_open': []}
        
        if 'stock.move' in [x[0] for x in models]:
            new_values = []
            Destruction_Report = trans_obj.tr_view(cr, 'Destruction Report', context)
            for v in values:
                if key == 'action' and v[1] in move_accepted_values[key2]:
                    new_values.append(v)
                elif context.get('_terp_view_name', False) == Destruction_Report:
                    new_values.append(v)
        elif context.get('picking_type', False) == 'incoming_shipment' and 'stock.picking' in [x[0] for x in models]:
            new_values = []
            for v in values:
                if key == 'action' and v[1] in incoming_accepted_values[key2]:
                    new_values.append(v)
        elif context.get('picking_type', False) == 'internal_move' and 'stock.picking' in [x[0] for x in models]:
            new_values = []
            for v in values:
                if key == 'action' and v[1] in internal_accepted_values[key2]:
                    new_values.append(v)
        elif context.get('picking_type', False) == 'delivery_order' and 'stock.picking' in [x[0] for x in models]:
            new_values = []
            for v in values:
                if key == 'action' and v[1] in delivery_accepted_values[key2]:
                    new_values.append(v)
        elif context.get('picking_type', False) == 'picking_ticket' and 'stock.picking' in [x[0] for x in models]:
            new_values = []
            for v in values:
                if key == 'action' and v[1] in picking_accepted_values[key2]:
                    new_values.append(v)
        return new_values

ir_values()
