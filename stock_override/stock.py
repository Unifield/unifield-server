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
    
    _columns = {'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
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

    _columns = {
        'state': fields.selection([
            ('draft', 'Draft'),
            ('auto', 'Waiting'),
            ('confirmed', 'Confirmed'),
            ('assigned', 'Available'),
            ('done', 'Closed'),
            ('cancel', 'Cancelled'),
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
    }
    
    _defaults = {'from_yml_test': lambda *a: False,
                 }
    
    def create(self, cr, uid, vals, context=None):
        '''
        create method for filling flag from yml tests
        '''
        if context is None:
            context = {}
        if context.get('update_mode') in ['init', 'update'] and 'from_yml_test' not in vals:
            logging.getLogger('init').info('PICKING: set from yml test to True')
            vals['from_yml_test'] = True
            
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
            
        return super(stock_picking, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the partner or the address according to the other
        '''
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
        
        return super(stock_picking, self).write(cr, uid, ids, vals, context=context)
    
    def on_change_partner(self, cr, uid, ids, partner_id, address_id, context=None):
        '''
        Change the delivery address when the partner change.
        '''
        v = {}
        d = {}
        
        if not partner_id:
            v.update({'address_id': False})
        else:
            d.update({'address_id': [('partner_id2', '=', partner_id)]})
            

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
    
    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        defaults = kwargs.get('defaults')
        assert defaults is not None, 'missing defaults'
        
        return defaults

    # @@@override stock>stock.py>stock_picking>do_partial
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial picking and moves done.
        @param partial_datas : Dictionary containing details of partial picking
                          like partner_id, address_id, delivery_date,
                          delivery moves with product_id, product_qty, uom
        @return: Dictionary of values
        """
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
        for pick in self.browse(cr, uid, ids, context=context):
            new_picking = None
            complete, too_many, too_few = [], [], []
            move_product_qty = {}
            prodlot_ids = {}
            product_avail = {}
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
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
                if (pick.type == 'in') and (move.product_id.cost_method == 'average'):
                    product = product_obj.browse(cr, uid, move.product_id.id)
                    move_currency_id = move.company_id.currency_id.id
                    context['currency_id'] = move_currency_id
                    qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)

                    if product.id in product_avail:
                        product_avail[product.id] += qty
                    else:
                        product_avail[product.id] = product.qty_available

                    if qty > 0:
                        new_price = currency_obj.compute(cr, uid, product_currency,
                                move_currency_id, product_price)
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
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [pick.id], {'backorder_id': new_picking})
                self.action_move(cr, uid, [new_picking])
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
                delivered_pack_id = new_picking
            else:
                self.action_move(cr, uid, [pick.id])
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                delivered_pack_id = pick.id

            delivered_pack = self.browse(cr, uid, delivered_pack_id, context=context)
            res[pick.id] = {'delivered_picking': delivered_pack.id or False}

        return res
    # @@@override end

    def action_done(self, cr, uid, ids, context=None):
        """
        Create automatically invoice
        """
        res = super(stock_picking, self).action_done(cr, uid, ids, context=context)
        if res:
            for sp in self.browse(cr, uid, ids):
                sp_type = False
                inv_type = False # by default action_invoice_create make an 'out_invoice'
                if sp.type == 'in' or sp.type == 'internal':
                    sp_type = 'purchase'
                    inv_type = 'in_invoice'
                elif sp.type == 'out':
                    sp_type = 'sale'
                    inv_type = 'out_invoice'
                journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', sp_type)])
                if not journal_ids:
                    raise osv.except_osv(_('Warning'), _('No %s journal found!') % (sp_type,))
                self.action_invoice_create(cr, uid, [sp.id], journal_ids[0], False, inv_type, {})
        return True

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

    _columns = {
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Not Available'), ('assigned', 'Available'), ('done', 'Closed'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True,
              help='When the stock move is created it is in the \'Draft\' state.\n After that, it is set to \'Not Available\' state if the scheduler did not find the products.\n When products are reserved it is set to \'Available\'.\n When the picking is done the state is \'Closed\'.\
              \nThe state is \'Waiting\' if the move is waiting for another one.'),
        'address_id': fields.many2one('res.partner.address', 'Delivery address', help="Address of partner", readonly=False, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, domain="[('partner_id', '=', partner_id)]"),
        'partner_id2': fields.many2one('res.partner', 'Partner', required=False),
        'already_confirmed': fields.boolean(string='Already confirmed'),
    }
    
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
        
        return super(stock_move, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the partner or the address according to the other
        '''
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
        
        return super(stock_move, self).write(cr, uid, ids, vals, context=context)
    
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
            if (move.picking_id.type == 'in') and (move.product_id.cost_method == 'average'):
                product = product_obj.browse(cr, uid, move.product_id.id)
                move_currency_id = move.company_id.currency_id.id
                context['currency_id'] = move_currency_id
                qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
                if qty > 0:
                    new_price = currency_obj.compute(cr, uid, product_currency,
                            move_currency_id, product_price)
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

stock_move()

#-----------------------------------------
#   Stock location
#-----------------------------------------
class stock_location(osv.osv):
    _name = 'stock.location'
    _inherit = 'stock.location'
    
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
