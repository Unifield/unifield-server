
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv
from tools.translate import _
import time
import netsvc

class create_picking(osv.osv_memory):
    _name = "create.picking"
    _description = "Create Picking"
    _columns = {
        'date': fields.datetime('Date', required=True),
        'product_moves_picking' : fields.one2many('stock.move.memory.picking', 'wizard_id', 'Moves'),
        'product_moves_ppl' : fields.one2many('stock.move.memory.ppl', 'wizard_id', 'Moves'),
        'product_moves_families' : fields.one2many('stock.move.memory.families', 'wizard_id', 'Pack Families'),
        'product_moves_returnproducts': fields.one2many('stock.move.memory.returnproducts', 'wizard_id', 'Return Products')
     }
    
    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}
        
        # we need the step info
        assert 'step' in context, 'Step not defined in context'
        step = context['step']
            
        pick_obj = self.pool.get('stock.picking')
        res = super(create_picking, self).default_get(cr, uid, fields, context=context)
        picking_ids = context.get('active_ids', [])
        if not picking_ids:
            return res

        result = []
        if step in ('create', 'validate', 'ppl1', 'returnproducts'):
            # memory moves wizards
            # data generated from stock.moves
            for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                result.extend(self.__create_partial_picking_memory(pick, context=context))
        elif step in ('ppl2'):
            # pack families wizard
            # data generated from previous wizard data
            for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                result.extend(self.__create_pack_families_memory(pick, context=context))

        if 'product_moves_picking' in fields and step in ('create', 'validate'):
            res.update({'product_moves_picking': result})
            
        if 'product_moves_ppl' in fields and step in ('ppl1'):
            res.update({'product_moves_ppl': result})
            
        if 'product_moves_returnproducts' in fields and step in ('returnproducts'):
            res.update({'product_moves_returnproducts': result})
            
        if 'product_moves_families' in fields and step in ('ppl2'):
            res.update({'product_moves_families': result})
            
        if 'date' in fields:
            res.update({'date': time.strftime('%Y-%m-%d %H:%M:%S')})
            
        return res
    
    def __create_partial_picking_memory(self, pick, context=None):
        '''
        generates the memory objects data depending on wizard step
        
        - wizard_id seems to be filled automatically
        '''
        assert context, 'No context defined'
        assert 'step' in context, 'No step defined in context'
        step = context['step']
        
        # list for the current pick object
        result = []
        for move in pick.move_lines:
            if move.state in ('done', 'cancel'):
                continue
            move_memory = {
                'product_id' : move.product_id.id,
                'asset_id': move.asset_id.id, 
                'quantity' : move.product_qty,
                'product_uom' : move.product_uom.id, 
                'prodlot_id' : move.prodlot_id.id, 
                'move_id' : move.id,
            }
            
            # the first wizard of ppl, we set default values as everything is packed in one pack
#            if step == 'ppl1':
#                move_memory.update({'qty_per_pack': move.product_qty, 'from_pack': 1, 'to_pack': 1})
            # append the created dict
            result.append(move_memory)
        
        # return the list of dictionaries
        return result
    
    def __create_pack_families_memory(self, pick, context=None):
        '''
        generates the memory objects data depending on wizard step
        
        - wizard_id seems to be filled automatically
        '''
        assert context, 'No context defined'
        assert 'step' in context, 'No step defined in context'
        step = context['step']
        assert 'partial_datas_ppl1' in context, 'No partial data from step1'
        partial_datas_ppl1 = context['partial_datas_ppl1']
        
        # list for the current pick object
        result = []
        from_packs = partial_datas_ppl1[pick.id].keys()
        # we want the lines sorted in from_pack order
        from_packs.sort()
        for from_pack in from_packs:
            for to_pack in partial_datas_ppl1[pick.id][from_pack]:
                family_memory = {
                                 'from_pack': from_pack,
                                 'to_pack': to_pack,}
            
                # append the created dict
                result.append(family_memory)
        
        # return the list of dictionaries
        return result
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        # integrity check
        assert context, 'No context defined'
        # call super
        result = super(create_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        # working objects
        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)
        assert 'step' in context, 'No step defined in context'
        step = context['step']

        if not picking_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result
        
        # get picking subtype
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            picking_subtype = pick.subtype
            
        # select field to display
        if picking_subtype == 'picking':
            field = 'picking'
        elif picking_subtype == 'ppl':
            if step == 'ppl1':
                field = 'ppl'
            elif step == 'ppl2':
                field = 'families'
            elif step == 'returnproducts':
                field = 'returnproducts'
        
        _moves_arch_lst = """<form string="%s">
                        <field name="date" invisible="1"/>
                        <separator colspan="4" string="%s"/>
                        <field name="product_moves_%s" colspan="4" nolabel="1" mode="tree,form"></field>
                        """ % (_('Process Document'), _('Products'), field)
        _moves_fields = result['fields']

        # add field related to picking type only
        _moves_fields.update({
                            'product_moves_' + field: {'relation': 'stock.move.memory.' + field, 'type' : 'one2many', 'string' : 'Product Moves'}, 
                            })

        # specify the button according to the screen
        # picking, two wizard steps
        # refactoring is needed here !
        if picking_subtype == 'picking':
            if step == 'create':
                button = ('do_create_picking', 'Create Picking')
            elif step == 'validate':
                button = ('do_validate_picking', 'Validate Picking')
        # ppl, two wizard steps
        elif picking_subtype == 'ppl':
            if step == 'ppl1':
                button = ('do_ppl1', 'Next')
            if step == 'ppl2':
                button = ('do_ppl2', 'Validate PPL')
            if step == 'returnproducts':
                button = ('do_return_products', 'Return')
                    
        else:
            button = ('undefined', 'Undefined')
                
        _moves_arch_lst += """
                <separator string="" colspan="4" />
                <label string="" colspan="2"/>
                <group col="3" colspan="2">
                <button icon='gtk-cancel' special="cancel"
                    string="_Cancel" />"""
                    
        if step == 'ppl2':
            _moves_arch_lst += """
                <button name="back_ppl1" string="previous"
                    colspan="1" type="object" icon="gtk-go-back" />"""
                    
        elif step == 'returnproducts':
            _moves_arch_lst += """
                <button name="select_all" string="Select All"
                    colspan="1" type="object" icon="terp_stock_symbol-selection" />"""
                    
        _moves_arch_lst += """
                <button name="%s" string="%s"
                    colspan="1" type="object" icon="gtk-go-forward" />
            </group>
        </form>"""%button
        
        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result
    
    def generate_move_as_key(self, cr, uid, ids, context=None):
        '''
        
        '''
        pass
    
    def generate_data_from_partial(self, cr, uid, ids, context=None):
        '''
        data is located in product_moves_ppl
        
        we generate the data structure from the first ppl wizard (ppl1)
        
        structure :
        {pick_id: {from_pack: {to_pack: {move_id: [{partial},]}}}}
        
        data are indexed by pack_id, then by pack_family information (from_pack/to_pack)
        and finally by move_id. Move_id indexing is added because within one
        pack sequence we can find the same move_id multiple time thanks to split function.
        
        with partial beeing the info for one stock.move.memory.ppl
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        
        pick_obj = self.pool.get('stock.picking')
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        # returned datas
        partial_datas_ppl1 = {}
        
        # picking ids
        picking_ids = context['active_ids']
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            # for each picking
            partial_datas_ppl1[pick.id] = {}
            # ppl moves
            memory_moves_list = partial.product_moves_ppl
            # organize data according to from pack / to pack
            for move in memory_moves_list:
                partial_datas_ppl1[pick.id] \
                    .setdefault(move.from_pack, {}) \
                    .setdefault(move.to_pack, {}) \
                    .setdefault(move.move_id.id, []).append({
                                                             'product_id': move.product_id.id,
                                                             'product_qty': move.quantity,
                                                             'product_uom': move.product_uom.id,
                                                             'prodlot_id': move.prodlot_id.id,
                                                             'asset_id': move.asset_id.id,
                                                             'move_id': move.move_id.id,
                                                             'qty_per_pack': move.qty_per_pack,
                                                             'from_pack': move.from_pack,
                                                             'to_pack': move.to_pack,
                                                             })
                
        return partial_datas_ppl1
    
    def update_data_from_partial(self, cr, uid, ids, context=None):
        '''
        update the list corresponding to moves for each sequence with ppl2 information
        
        generated structure from step ppl1 wizard is updated with step ppl2 wizard,
        the partial dictionaries are updated with pack_family related information
        
        structure :
        {pick_id: {from_pack: {to_pack: {move_id: [{partial},]}}}}
        '''
        assert context, 'no context defined'
        assert 'partial_datas_ppl1' in context, 'partial_datas_ppl1 not in context'
        
        pick_obj = self.pool.get('stock.picking')
        family_obj = self.pool.get('stock.move.memory.families')
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        # ppl families
        memory_families_list = partial.product_moves_families
        for family in memory_families_list:
            a=1
        # returned datas
        partial_datas_ppl1 = context['partial_datas_ppl1']
        
        # picking ids
        picking_ids = context['active_ids']
        for picking_id in picking_ids:
            # for each picking
            for from_pack in partial_datas_ppl1[picking_id]:
                for to_pack in partial_datas_ppl1[picking_id][from_pack]:
                    # find corresponding sequence info
                    family_ids = family_obj.search(cr, uid, [('wizard_id', '=', ids[0]), ('from_pack', '=', from_pack), ('to_pack', '=', to_pack)], context=context)
                    # only one line should match
                    assert len(family_ids) == 1, 'No the good number of families : %i'%len(family_ids)
                    family = family_obj.read(cr, uid, family_ids, ['pack_type', 'length', 'width', 'height', 'weight'], context=context)[0]
                    # remove id key
                    family.pop('id')
                    for move in partial_datas_ppl1[picking_id][from_pack][to_pack]:
                        for partial in partial_datas_ppl1[picking_id][from_pack][to_pack][move]:
                            partial.update(family)
        
    def do_create_picking(self, cr, uid, ids, context=None):
        '''
        create the picking ticket from selected stock moves
        -> only related to 'out' type stock.picking
        
        - transform data from wizard
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        # picking ids
        picking_ids = context['active_ids']
        assert len(picking_ids) == 1, 'Number of picking ids is not valid (%i)' % len(picking_ids)
        picking_id = picking_ids[0]
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        # date of the picking ticket creation, not used for now
        partial_datas = {}
#        partial_datas = {
#            'delivery_date' : partial.date
#        }
        
        pick = pick_obj.browse(cr, uid, picking_id, context=context)
        # out moves for delivery
        memory_moves_list = partial.product_moves_picking
        # organize data according to move id
        for move in memory_moves_list:
            # only take into account if the quantity is greater than 0
            if move.quantity:
                partial_datas.setdefault(move.move_id.id, []).append({'product_id': move.product_id.id,
                                                                      'product_qty': move.quantity,
                                                                      'product_uom': move.product_uom.id,
                                                                      'prodlot_id': move.prodlot_id.id,
                                                                      'asset_id': move.asset_id.id,
                                                                      })
    
        # create the new picking object
        # TODO origin is not copied if name is not supplied as default.
        #      create a new sequence for each draft picking ticket, and bricoler with draft ref or something for traceability
        sequence = pick.sequence_id
        ticket_number = sequence.get_id(test='id', context=context)
        new_pick_id = pick_obj.copy(cr, uid, picking_id, {'name': pick.name + '-' + ticket_number,
                                                          'backorder_id': picking_id,
                                                          'move_lines': []}, context=context)
        # create stock moves corresponding to partial datas
        # browse returns a list of browse object in the same order as move_ids
        # for now, each new line from the wizard corresponds to a new stock.move
        # it could be interesting to regroup according to production lot/asset id
        # TODO refactoring this load is useless -> load the move object in the first loop for in browse( keys() )
        move_ids = partial_datas.keys()
        browse_moves = move_obj.browse(cr, uid, move_ids, context=context)
        moves = dict(zip(move_ids, browse_moves))
        for move in partial_datas:
            # qty selected
            count = 0
            # initial qty
            initial_qty = moves[move].product_qty
            for partial in partial_datas[move]:
                # integrity check
                partial['product_id'] == moves[move].product_id.id
                partial['product_uom'] == moves[move].product_uom.id
                # the quantity
                count = count + partial['product_qty']
                # copy the stock move and set the quantity
                new_move = move_obj.copy(cr, uid, move, {'picking_id': new_pick_id,
                                                         'product_qty': partial['product_qty'],
                                                         'prodlot_id': partial['prodlot_id'],
                                                         'asset_id': partial['asset_id'],
                                                         'backmove_id': move}, context=context)
            # decrement the initial move, cannot be less than zero
            initial_qty = max(initial_qty - count, 0)
            move_obj.write(cr, uid, [move], {'product_qty': initial_qty}, context=context)
            
        # confirm the new picking ticket
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', new_pick_id, 'button_confirm', cr)
        # we check availability - could be available or not
        pick_obj.force_assign(cr, uid, [new_pick_id])
        
        # TODO which behavior
        return {'type': 'ir.actions.act_window_close'}
        # display newly created picking ticket
        return {
            'name':_("Picking Ticket"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'stock.picking',
            'res_id': new_pick_id,
            'type': 'ir.actions.act_window',
            'target': 'crush',
        }
        
    def do_validate_picking(self, cr, uid, ids, context=None):
        '''
        create the picking ticket from selected stock moves
        -> only related to 'out' type stock.picking
        
        - transform data from wizard
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        
        # data container
        # date of the picking ticket creation, not used for now
            #partial_datas = {
            #                 'delivery_date' : partial.date
            #}
        partial_datas = {}
        
        # picking ids
        picking_ids = context['active_ids']
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            # for each picking
            partial_datas[pick.id] = {}
            # out moves for delivery
            memory_moves_list = partial.product_moves_picking
            # organize data according to move id
            for move in memory_moves_list:
                
                partial_datas[pick.id].setdefault(move.move_id.id, []).append({'product_id': move.product_id.id,
                                                                       'product_qty': move.quantity,
                                                                       'product_uom': move.product_uom.id,
                                                                       'prodlot_id': move.prodlot_id.id,
                                                                       'asset_id': move.asset_id.id,
                                                                       })
            
            # create stock moves corresponding to partial datas
            # browse returns a list of browse object in the same order as move_ids
            move_ids = partial_datas[pick.id].keys()
            browse_moves = move_obj.browse(cr, uid, move_ids, context=context)
            moves = dict(zip(move_ids, browse_moves))
            
            for move in partial_datas[pick.id]:
                # qty selected
                count = 0
                # flag to update the first move
                first = True
                # initial qty
                initial_qty = moves[move].product_qty
                for partial in partial_datas[pick.id][move]:
                    # integrity check
                    partial['product_id'] == moves[move].product_id.id
                    partial['product_uom'] == moves[move].product_uom.id
                    # the quantity
                    count = count + partial['product_qty']
                    if first:
                        first = False
                        # update existing move
                        move_obj.write(cr, uid, [move], {'product_qty': partial['product_qty'],
                                                         'prodlot_id': partial['prodlot_id'],
                                                         'asset_id': partial['asset_id']}, context=context)
                    else:
                        # copy the stock move and set the quantity
                        new_move = move_obj.copy(cr, uid, move, {'state': 'assigned',
                                                                 'product_qty': partial['product_qty'],
                                                                 'prodlot_id': partial['prodlot_id'],
                                                                 'asset_id': partial['asset_id']}, context=context)
                # decrement the initial move, cannot be less than zero
                diff_qty = initial_qty - count
                if diff_qty != 0:
                    backorder_id = pick.backorder_id.id
                    assert backorder_id, 'No backorder defined.'
                    original_moves = move_obj.search(cr, uid, [('picking_id', '=', backorder_id),
                                                              ('product_id', '=', moves[move].product_id.id),
                                                              ('product_uom', '=', moves[move].product_uom.id)])
                    assert len(original_moves) == 1, 'No corresponding stock_move have been found in draft picking ticket for product %s and UOM %s'%(moves[move].product_id.name, moves[move].product_uom.name)
                    backorder_qty = move_obj.read(cr, uid, original_moves, ['product_qty'], context=context)[0]['product_qty']
                    backorder_qty = max(backorder_qty + diff_qty, 0)
                    move_obj.write(cr, uid, original_moves, {'product_qty': backorder_qty}, context=context)
        
            # create the new ppl object
            ppl_number = pick.name.split("/")[1]
            new_ppl_id = pick_obj.copy(cr, uid, pick.id, {'name': 'PPL/' + ppl_number,
                                                          'subtype': 'ppl',
                                                          'previous_step_id': pick.id,
                                                          'backorder_id': False}, context=context)
            new_ppl = pick_obj.browse(cr, uid, new_ppl_id, context=context)
            # update locations of stock moves - if the move quantity is equal to zero, the state is removed
            for move in new_ppl.move_lines:
                if move.product_qty:
                    move_obj.write(cr, uid, [move.id], {'initial_location': move.location_id.id,
                                                        'location_id': move.location_dest_id.id,
                                                        'location_dest_id': new_ppl.sale_id.shop_id.warehouse_id.lot_dispatch_id.id}, context=context)
                else:
                    move_obj.unlink(cr, uid, [move.id], context=context)
            
            wf_service.trg_validate(uid, 'stock.picking', new_ppl_id, 'button_confirm', cr)
            # simulate check assign button, as stock move must be available
            pick_obj.force_assign(cr, uid, [new_ppl_id])
            # trigger standard workflow
            pick_obj.action_move(cr, uid, [pick.id])
            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
        
        # close wizard
        return {'type': 'ir.actions.act_window_close'}
    
    def do_return_products(self, cr, uid, ids, context=None):
        '''
        process data and call do_return_products from stock picking
        
        data structure:
        {picking_id: {move_id: {data}}}
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        # partial data from wizard
        partial = self.browse(cr, uid, ids[0], context=context)
        partial_datas = {}
        
        # picking ids
        picking_ids = context['active_ids']
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            # for each picking
            partial_datas[pick.id] = {}
            # out moves for delivery
            memory_moves_list = partial.product_moves_returnproducts
            # organize data according to move id
            for move in memory_moves_list:
                if move.qty_to_return:
                    partial_datas[pick.id][move.move_id.id] = {'product_id': move.product_id.id,
                                                              'asset_id': move.asset_id.id,
                                                              'product_qty': move.quantity,
                                                              'product_uom': move.product_uom.id,
                                                              'prodlot_id': move.prodlot_id.id,
                                                              'qty_to_return': move.qty_to_return,
                                                              }
        
        return pick_obj.do_return_products(cr, uid, picking_ids, context=dict(context, partial_datas=partial_datas))
        
    def do_ppl1(self, cr, uid, ids, context=None):
        '''
        - generate data
        - call stock.picking>do_ppl1
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        
        pick_obj = self.pool.get('stock.picking')
        # picking ids
        picking_ids = context['active_ids']
        # generate data structure
        partial_datas_ppl1 = self.generate_data_from_partial(cr, uid, ids, context=context)
        # call stock_picking method which returns action call
        return pick_obj.do_ppl1(cr, uid, picking_ids, context=dict(context, partial_datas_ppl1=partial_datas_ppl1))
    
    def back_ppl1(self, cr, uid, ids, context=None):
        '''
        call back ppl1 step wizard
        '''
        # we need the context for the wizard switch
        assert context, 'no context defined'
        
        pick_obj = self.pool.get('stock.picking')
        
        # no data for type 'back'
        return pick_obj.open_wizard(cr, uid, context['active_ids'], type='back', context=context)
        
    def do_ppl2(self, cr, uid, ids, context=None):
        '''
        - update partial_datas_ppl1
        - call stock.picking>do_ppl2
        '''
        # integrity check
        assert context, 'no context, method call is wrong'
        assert 'active_ids' in context, 'No picking ids in context. Action call is wrong'
        
        pick_obj = self.pool.get('stock.picking')
        # picking ids
        picking_ids = context['active_ids']
        # update data structure
        self.update_data_from_partial(cr, uid, ids, context=context)
        # call stock_picking method which returns action call
        return pick_obj.do_ppl2(cr, uid, picking_ids, context=context)

create_picking()
