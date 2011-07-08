# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import netsvc

class stock_warehouse(osv.osv):
    '''
    add new packing, dispatch and distribution locations for input
    '''
    _inherit = "stock.warehouse"
    _name = "stock.warehouse"
    _columns = {
        'lot_packing_id': fields.many2one('stock.location', 'Location Packing', required=True, domain=[('usage','<>','view')]),
        'lot_dispatch_id': fields.many2one('stock.location', 'Location Dispatch', required=True, domain=[('usage','<>','view')]),
        'lot_distribution_id': fields.many2one('stock.location', 'Location Distribution', required=True, domain=[('usage','<>','view')]),
    }

stock_warehouse()


class pack_type(osv.osv):
    '''
    pack type corresponding to a type of pack (name, length, width, height)
    '''
    _name = 'pack.type'
    _description = 'Pack Type'
    _columns = {'name': fields.char(string='Name', size=1024),
                'length': fields.float(digits=(16,2), string='Length [cm]'),
                'width': fields.float(digits=(16,2), string='Width [cm]'),
                'height': fields.float(digits=(16,2), string='Height [cm]'),
                }

pack_type()


class shipment(osv.osv):
    '''
    a shipment presents the data from grouped stock moves in a 'sequence' way
    '''
    _name = 'shipment'
    _description = 'represents a group of pack families'
    _columns = {'name': fields.char(string='Reference', size=1024),
                'date': fields.date(string='Date'),
                'transport_type': fields.selection([('by_road', 'By road')],
                                                   string="Transport Type", readonly=True),
                'state': fields.selection([
                                           ('draft', 'Draft'),
                                           ('packed', 'Packed'),
                                           ('shipped', 'Shipped'),
                                           ('done', 'Done'),
                                           ('cancel', 'Canceled')], string='State', readonly=True, select=True),
                'address_id': fields.many2one('res.partner.address', 'Address', help="Address of customer"),
                'partner_id': fields.related('address_id', 'partner_id', type='many2one', relation='res.partner', string='Customer', store=True),
                }
    _defaults = {'state': 'draft'}
    
    def create_shipment(self, cr, uid, ids, context=None):
        '''
        open the wizard to create (partial) shipment
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
        
        # data
        name = _("Create Shipment")
        model = 'create.picking'
        step = 'create'
        # open the selected wizard
        return self.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)

shipment()


class pack_family(osv.osv):
    '''
    a pack family represents a sequence of homogeneous packs
    '''
    _name = 'pack.family'
    _description = 'represents a pack family'
    _columns = {'name': fields.char(string='Reference', size=1024),
                'shipment_id': fields.many2one('shipment', string='Shipment'),
                'sale_order_id': fields.many2one('sale.order', string="Sale Order Ref"),
                'ppl_id': fields.many2one('stock.picking', string="PPL Ref"),
                'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                'pack_type': fields.many2one('pack.type', string='Pack Type'),
                'length' : fields.float(digits=(16,2), string='Length [cm]'),
                'width' : fields.float(digits=(16,2), string='Width [cm]'),
                'height' : fields.float(digits=(16,2), string='Height [cm]'),
                'weight' : fields.float(digits=(16,2), string='Weight p.p [kg]'),
                'num_of_packs': fields.integer(string='#Packs'),
                'total_weight' : fields.float(digits=(16,2), string='Total Weight [kg]'),
                'move_lines': fields.one2many('stock.move', 'pack_family_id', string="Stock Moves"),
                'state': fields.selection([
                                           ('draft', 'Draft'),
                                           ('packed', 'Packed'),
                                           ('shipped', 'Shipped'),
                                           ('done', 'Done'),
                                           ('cancel', 'Canceled')], string='State', readonly=True, select=True),
                }
    _defaults = {'state': 'draft'}

pack_family()


class shipment(osv.osv):
    '''
    add pack_family_ids
    '''
    _inherit = 'shipment'
    _columns = {'pack_family_ids': fields.one2many('pack.family', 'shipment_id', string='Pack Families')}

shipment()


class stock_picking(osv.osv):
    '''
    override stock picking to add new attributes
    - flow_type: the type of flow (full, quick)
    - subtype: the subtype of picking object (picking, ppl, packing)
    - previous_step_id: the id of picking object of the previous step, picking for ppl, ppl for packing
    '''
    _inherit = 'stock.picking'
    _name = 'stock.picking'
    _columns = {'flow_type': fields.selection([('full', 'Full'),('quick', 'Quick')], string='Flow Type'),
                'subtype': fields.selection([('picking', 'Picking'),('ppl', 'PPL'),('packing', 'Packing')], string='Subtype'),
                'previous_step_id': fields.many2one('stock.picking', 'Previous step'),
                'shipment_id': fields.many2one('shipment', string='Shipment'),
                }
    
    def generate_data_from_picking_for_pack_family(self, cr, uid, pick_ids, context=None):
        '''
        generate the data structure from the stock.picking object
        
        one data for each move_id - here is the difference with data generated from partial
        
        structure:
            {pick_id: {from_pack: {to_pack: {move_id: {data}}}}}
            
        if the move has a quantity equal to 0, it means that no pack are available,
        these moves are therefore not taken into account for the pack families generation
        
        TODO: integrity constraints
        
        Note: why the same dictionary is repeated n times for n moves, because
        it is directly used when we create the pack families. could be refactored
        with one dic per from/to with a 'move_ids' entry
        '''
        result = {}
        
        for pick in self.browse(cr, uid, pick_ids, context=context):
            result[pick.id] = {}
            for move in pick.move_lines:
                if move.product_qty > 0.0:
                    result[pick.id] \
                        .setdefault(move.from_pack, {}) \
                        .setdefault(move.to_pack, {})[move.id] = {'sale_order_id': pick.sale_id.id,
                                                                  'ppl_id': pick.previous_step_id.id,
                                                                  'from_pack': move.from_pack,
                                                                  'to_pack': move.to_pack,
                                                                  'pack_type': move.pack_type.id,
                                                                  'length': move.length,
                                                                  'width': move.width,
                                                                  'height': move.height,
                                                                  'weight': move.weight,
                                                                  }
        
        return result
    
    def create_pack_families_from_data(self, cr, uid, data, shipment_id, context=None):
        '''
        create pack families corresponding to data parameter
        
        - we can have the data from many picks, all corresponding pack families are
          created in shipment_id
        '''
        # picking ids
        picking_ids = data.keys()
        pack_family_obj = self.pool.get('pack.family')
        move_obj = self.pool.get('stock.move')
        
        for pick_id in picking_ids:
            for from_pack in data[pick_id]:
                for to_pack in data[pick_id][from_pack]:
                    # create the pack family object
                    pack_family_id = False
                    for move in data[pick_id][from_pack][to_pack]:
                        # create the pack family
                        if not pack_family_id:
                            move_data = data[pick_id][from_pack][to_pack][move]
                            move_data.update({'name': 'PF/xxxx', 'shipment_id': shipment_id})
                            pack_family_id = pack_family_obj.create(cr, uid, move_data, context=context)
                            
                        # update the moves concerned by the pack_family:
                        values = {'pack_family_id': pack_family_id}
                        move_obj.write(cr, uid, [move], values, context=context)
        
    def create(self, cr, uid, vals, context=None):
        '''
        creation of a stock.picking of subtype 'packing' triggers
        special behavior :
         - creation of corresponding shipment
        '''
        # shipment object
        shipment_obj = self.pool.get('shipment')
        
        # create packing object
        pick_id = super(stock_picking, self).create(cr, uid, vals, context=context)
        
        if 'subtype' in vals and vals['subtype'] == 'packing':
            # creation of a new packing
            assert 'state' in vals, 'State is missing'
            
            if vals['state'] == 'draft':
                # creation of packing after ppl validation
                # generate data from stock.picking object
                data = self.generate_data_from_picking_for_pack_family(cr, uid, [pick_id], context=context)
                
                # find a existing shipment or create one - depends on new pick state
                shipment_ids = shipment_obj.search(cr, uid, [('state', '=', 'draft'), ('address_id', '=', vals['address_id'])])
                # only one 'draft' shipment should be available
                assert len(shipment_ids) in (0, 1), 'Only one draft shipment should be available for a given address at a time'
                
                if not len(shipment_ids):
                    # no shipment, create one
                    values = {'name': 'SHIP/xxxx', 'state': 'draft', 'address_id': vals['address_id']}
                    shipment_id = shipment_obj.create(cr, uid, values, context=context)
                else:
                    shipment_id = shipment_ids[0]
                    
                # update the new pick with shipment_id
                self.write(cr, uid, pick_id, {'shipment_id': shipment_id}, context=context)
                
                # create the pack_familiy objects from stock.picking object
                self.create_pack_families_from_data(cr, uid, data, shipment_id, context=context)
                
            elif vals['state'] == 'assigned':
                assert False, 'Not yet implemented'
                
            else:
                assert False, 'Should not reach this line'
            
        return pick_id
    
    #@@@override stock
    def action_assign(self, cr, uid, ids, *args):
        '''
        override to remove the error message, return False instead
        '''
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines if x.state == 'confirmed']
            if not move_ids:
                return False
            self.pool.get('stock.move').action_assign(cr, uid, move_ids)
        return True
    #@@@end
    
    def open_wizard(self, cr, uid, ids, name=False, model=False, step='default', type='create', context=None):
        '''
        WARNING : IDS CORRESPOND TO ***PICKING IDS*** take care when calling the method
        return the newly created wizard's id
        name, model, step are mandatory only for type 'create'
        '''
        if context is None:
            context = {}
        
        if type == 'create':
            assert name, 'type "create" and no name defined'
            assert model, 'type "create" and no model defined'
            assert step, 'type "create" and no step defined'
            # create the memory object - passing the picking id to it through context
            wizard_id = self.pool.get(model).create(
                cr, uid, {}, context=dict(context,
                                          active_ids=ids,
                                          model=model,
                                          step=step,
                                          back_model=context.get('model', False),
                                          back_wizard_ids=context.get('wizard_ids', False),
                                          back_wizard_name=context.get('wizard_name', False),
                                          back_step=context.get('step', False),
                                          wizard_name=name))
        
        elif type == 'back':
            # open the previous wizard
            assert context['back_wizard_ids'], 'no back_wizard_ids defined'
            wizard_id = context['back_wizard_ids'][0]
            assert context['back_wizard_name'], 'no back_wizard_name defined'
            name = context['back_wizard_name']
            assert context['back_model'], 'no back_model defined'
            model = context['back_model']
            assert context['back_step'], 'no back_step defined'
            step = context['back_step']
            
        # call action to wizard view
        return {
            'name': name,
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': model,
            'res_id': wizard_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context,
                            active_ids=ids,
                            wizard_ids=[wizard_id],
                            model=model,
                            step=step,
                            back_model=context.get('model', False),
                            back_wizard_ids=context.get('wizard_ids', False),
                            back_wizard_name=context.get('wizard_name', False),
                            back_step=context.get('step', False),
                            wizard_name=name)
        }
    
    def create_picking(self, cr, uid, ids, context=None):
        '''
        open the wizard to create (partial) picking tickets
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
        
        # data
        name = _("Create Picking Ticket")
        model = 'create.picking'
        step = 'create'
        # open the selected wizard
        return self.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
        
    def do_create_picking(self, cr, uid, ids, partial_datas, context=None):
        '''
        create the picking ticket from selected stock moves
        
        move here the logic of create picking
        available for picking loop
        '''
        pass
        
    def validate_picking(self, cr, uid, ids, context=None):
        '''
        validate the picking ticket
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        # data
        name = _("Validate Picking Ticket")
        model = 'create.picking'
        step = 'validate'
            
        # open the selected wizard
        return self.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
        
    def do_validate_picking(self, cr, uid, ids, partial_datas, context=None):
        '''
        validate the picking ticket from selected stock moves
        
        move here the logic of validate picking
        available for picking loop
        '''
        pass
#        for pick in..
#        
#            ...
#        
#            self.action_move(cr, uid, [pick.id])
#            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
#        
    def ppl(self, cr, uid, ids, context=None):
        '''
        pack the ppl - open the ppl step1 wizard
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}
            
        # data
        name = _("PPL Information - step1")
        model = 'create.picking'
        step = 'ppl1'
        
        # open the selected wizard
        return self.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
        
    def do_ppl1(self, cr, uid, ids, context=None):
        '''
        - receives generated data from ppl in context
        - call action to ppl2 step with partial_datas_ppl1 in context
        - ids are the picking ids
        '''
        # we need the context for the wizard switch
        assert context, 'No context defined'
            
        # data
        name = _("PPL Information - step2")
        model = 'create.picking'
        step = 'ppl2'
        
        # open the selected wizard
        return self.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=context)
        
    def do_ppl2(self, cr, uid, ids, context=None):
        '''
        finalize the ppl logic
        '''
        # integrity check
        assert context, 'context not defined'
        assert 'partial_datas_ppl1' in context, 'partial_datas_ppl1 no defined in context'
        
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        # data from wizard
        partial_datas_ppl = context['partial_datas_ppl1']
        # picking ids from ids must be equal to picking ids from partial datas
        assert set(ids) == set(partial_datas_ppl.keys()), 'picking ids from ids and partial do not match'
        
        # update existing stock moves - create new one if split occurred
        # for each pick
        for pick in self.browse(cr, uid, ids, context=context):
            # integrity check on move_ids - moves ids from picking and partial must be the same
            from_pick = [move.id for move in pick.move_lines]
            from_partial = []
            # the list of updated stock.moves
            # if a stock.move is updated, the next time a new move is created
            updated = {}
            # load moves data
            # browse returns a list of browse object in the same order as from_partial
            browse_moves = move_obj.browse(cr, uid, from_pick, context=context)
            moves = dict(zip(from_pick, browse_moves))
            # loop through data
            for from_pack in partial_datas_ppl[pick.id]:
                for to_pack in partial_datas_ppl[pick.id][from_pack]:
                    for move in partial_datas_ppl[pick.id][from_pack][to_pack]:
                        # integrity check
                        from_partial.append(move)
                        for partial in partial_datas_ppl[pick.id][from_pack][to_pack][move]:
                            # {'asset_id': False, 'weight': False, 'product_id': 77, 'product_uom': 1, 'pack_type': False, 'length': False, 'to_pack': 1, 'height': False, 'from_pack': 1, 'prodlot_id': False, 'qty_per_pack': 18.0, 'product_qty': 18.0, 'width': False, 'move_id': 179}
                            # integrity check
                            partial['product_id'] == moves[move].product_id.id
                            partial['asset_id'] == moves[move].asset_id.id
                            partial['product_uom'] == moves[move].product_uom.id
                            partial['prodlot_id'] == moves[move].prodlot_id.id
                            # dictionary of new values, used for creation or update
                            fields = ['product_qty', 'qty_per_pack', 'from_pack', 'to_pack', 'pack_type', 'length', 'width', 'height', 'weight']
                            values = dict(zip(fields, [eval('partial["%s"]'%x) for x in fields]))
                            
                            if move in updated:
                                # if already updated, we create a new stock.move
                                updated[move]['partial_qty'] += partial['product_qty']
                                # force state to 'assigned'
                                values.update(state='assigned')
                                # copy stock.move with new product_qty, qty_per_pack. from_pack, to_pack, pack_type, length, width, height, weight
                                move_obj.copy(cr, uid, move, values, context=context)
                            else:
                                # update the existing stock move
                                updated[move] = {'initial': moves[move].product_qty, 'partial_qty': partial['product_qty']}
                                move_obj.write(cr, uid, [move], values, context=context)
        
            # integrity check - all moves are treated and no more
            assert set(from_pick) == set(from_partial), 'move_ids are not equal pick:%s - partial:%s'(set(from_pick), set(from_partial))
            # quantities are right
            assert all([updated[m]['initial'] == updated[m]['partial_qty'] for m in updated.keys()]), 'initial quantity is not equal to the sum of partial quantities (%s).'%(updated)
            # copy to 'packing' stock.picking
            # draft shipment is automatically created or updated if a shipment already
            new_packing_id = self.copy(cr, uid, pick.id, {'subtype': 'packing', 'previous_step_id': pick.id}, context=context)
            self.write(cr, uid, [new_packing_id], {'origin': pick.origin}, context=context)
            # update locations of stock moves and state as the picking stay at 'draft' state
            new_packing = self.browse(cr, uid, new_packing_id, context=context)
            for move in new_packing.move_lines:
                move.write({'state': 'assigned',
                            'location_id': new_packing.sale_id.shop_id.warehouse_id.lot_dispatch_id.id,
                            'location_dest_id': new_packing.sale_id.shop_id.warehouse_id.lot_distribution_id.id}, context=context)
            
            # trigger standard workflow
            self.action_move(cr, uid, [pick.id])
            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
        
        # close wizard
        return {'type': 'ir.actions.act_window_close'}
            

stock_picking()


class stock_move(osv.osv):
    '''
    stock move
    '''
    _inherit = 'stock.move'
    _name = 'stock.move'
    
    def _product_available(self, cr, uid, ids, field_names=None, arg=False, context=None):
        '''
        facade for product_available function from product (stock)
        '''
        # get the corresponding product ids
        result = {}
        for d in self.read(cr, uid, ids, ['product_id'], context):
            result[d['id']] = d['product_id'][0]
        
        # get the virtual stock identified by product ids
        virtual = self.pool.get('product.product')._product_available(cr, uid, result.values(), field_names, arg, context)
        
        # replace product ids by corresponding stock move id
        result = dict([id, virtual[result[id]]] for id in result.keys())
        return result
    
    _columns = {'virtual_available': fields.function(_product_available, method=True, type='float', string='Virtual Stock', help="Future stock for this product according to the selected locations or all internal if none have been selected. Computed as: Real Stock - Outgoing + Incoming.", multi='qty_available', digits_compute=dp.get_precision('Product UoM')),
                'qty_per_pack': fields.integer(string='Qty p.p'),
                'from_pack': fields.integer(string='From p.'),
                'to_pack': fields.integer(string='To p.'),
                'pack_type': fields.many2one('pack.type', string='Pack Type'),
                'length' : fields.float(digits=(16,2), string='Length [cm]'),
                'width' : fields.float(digits=(16,2), string='Width [cm]'),
                'height' : fields.float(digits=(16,2), string='Height [cm]'),
                'weight' : fields.float(digits=(16,2), string='Weight p.p [kg]'),
                'pack_family_id': fields.many2one('pack.family', string='Pack Family'),
                }
    
#    _constraints = [
#        (_check_weight,
#            'You must assign an asset for this product',
#            ['asset_id']),]

stock_move()


class sale_order(osv.osv):
    '''
    re-override to modify behavior for outgoing workflow
    '''
    _inherit = 'sale.order'
    _name = 'sale.order'

    # @@@override@sale_override.sale.order.action_ship_create
    def action_ship_create(self, cr, uid, ids, *args, **kwargs):
        """
        - no call to confirmation for picking object's workflow
        - fill the new picking attributes (flow_type: 'full', subtype: 'picking')
        - the picking state is 'draft'
        - the move state is 'confirmed'
        """
        wf_service = netsvc.LocalService("workflow")
        picking_id = False
        move_obj = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        for order in self.browse(cr, uid, ids, context={}):
            proc_ids = []
            output_id = order.shop_id.warehouse_id.lot_packing_id.id
            picking_id = False
            for line in order.order_line:
                proc_id = False
                date_planned = datetime.now() + relativedelta(days=line.delay or 0.0)
                date_planned = (date_planned - timedelta(days=company.security_lead)).strftime('%Y-%m-%d %H:%M:%S')

                if line.state == 'done':
                    continue
                move_id = False
                if line.product_id and line.product_id.product_tmpl_id.type in ('product', 'consu') and not line.order_id.procurement_request:
                    location_id = order.shop_id.warehouse_id.lot_stock_id.id
                    if not picking_id:
                        pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.out')
                        picking_id = self.pool.get('stock.picking').create(cr, uid, {
                            'name': pick_name,
                            'origin': order.name,
                            'type': 'out',
                            # 'state': 'auto',
                            'state': 'draft',
                            'move_type': order.picking_policy,
                            'sale_id': order.id,
                            'address_id': order.partner_shipping_id.id,
                            'note': order.note,
                            'invoice_state': (order.order_policy=='picking' and '2binvoiced') or 'none',
                            'company_id': order.company_id.id,
                            # subtype
                            'subtype': 'picking',
                            # flow type
                            'flow_type': 'full',
                        })
                    move_data =  {
                        'name': line.name[:64],
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
                        'address_id': line.address_allotment_id.id or order.partner_shipping_id.id,
                        'location_id': location_id,
                        'location_dest_id': output_id,
                        'sale_line_id': line.id,
                        'tracking_id': False,
                        #'state': 'draft',
                        'state': 'confirmed',
                        #'state': 'waiting',
                        'note': line.notes,
                        'company_id': order.company_id.id,
                    }
                    move_data = self._hook_ship_create_stock_move(cr, uid, ids, move_data, line, *args, **kwargs)
                    move_id = self.pool.get('stock.move').create(cr, uid, move_data)

                if line.product_id:
                    proc_data = {
                        'name': line.name,
                        'origin': order.name,
                        'date_planned': date_planned,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': (line.product_uos and line.product_uos_qty)\
                                or line.product_uom_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                        'procure_method': line.type,
                        'move_id': move_id,
                        'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                        'company_id': order.company_id.id,
                    }
                    proc_data = self._hook_ship_create_procurement_order(cr, uid, ids, proc_data, line, *args, **kwargs)
                    proc_id = self.pool.get('procurement.order').create(cr, uid, proc_data)
                    proc_ids.append(proc_id)
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], {'procurement_id': proc_id})
                    if order.state == 'shipping_except':
                        for pick in order.picking_ids:
                            for move in pick.move_lines:
                                if move.state == 'cancel':
                                    mov_ids = move_obj.search(cr, uid, [('state', '=', 'cancel'),('sale_line_id', '=', line.id),('picking_id', '=', pick.id)])
                                    if mov_ids:
                                        for mov in move_obj.browse(cr, uid, mov_ids):
                                            move_obj.write(cr, uid, [move_id], {'product_qty': mov.product_qty, 'product_uos_qty': mov.product_uos_qty})
                                            proc_obj.write(cr, uid, [proc_id], {'product_qty': mov.product_qty, 'product_uos_qty': mov.product_uos_qty})

            val = {}

            if picking_id:
                # the picking is kept in 'draft' state
                #wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
                self.pool.get('stock.picking').log_picking(cr, uid, [picking_id])

            for proc_id in proc_ids:
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                if order.state == 'proc_progress':
                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)

            if order.state == 'shipping_except':
                val['state'] = 'progress'
                val['shipped'] = False

                if (order.order_policy == 'manual'):
                    for line in order.order_line:
                        if (not line.invoiced) and (line.state not in ('cancel', 'draft')):
                            val['state'] = 'manual'
                            break
            self.write(cr, uid, [order.id], val)
        return True
        # @@@end

sale_order()
