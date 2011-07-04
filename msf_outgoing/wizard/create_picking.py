
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
            
        pick_obj = self.pool.get('stock.picking')
        res = super(create_picking, self).default_get(cr, uid, fields, context=context)
        picking_ids = context.get('active_ids', [])
        if not picking_ids:
            return res

        result = []
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            for m in pick.move_lines:
                if m.state in ('done', 'cancel'):
                    continue
                result.append(self.__create_partial_picking_memory(m))

        if 'product_moves_picking' in fields:
            res.update({'product_moves_picking': result})
        if 'product_moves_ppl' in fields:
            res.update({'product_moves_ppl': result})
        if 'date' in fields:
            res.update({'date': time.strftime('%Y-%m-%d %H:%M:%S')})
        return res
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = super(create_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
       
        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)

        if not picking_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result
        
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            picking_subtype = pick.subtype
        
        _moves_arch_lst = """<form string="%s">
                        <field name="date" invisible="1"/>
                        <separator colspan="4" string="%s"/>
                        <field name="product_moves_%s" colspan="4" nolabel="1"></field>
                        """ % (_('Process Document'), _('Products'), picking_subtype)
        _moves_fields = result['fields']

        # add field related to picking type only
        _moves_fields.update({
                            'product_moves_' + picking_subtype: {'relation': 'stock.move.memory.' + picking_subtype, 'type' : 'one2many', 'string' : 'Product Moves'}, 
                            })

        # specify the button according to the screen
        # picking, two wizard steps
        if picking_subtype == 'picking':
            if context['step'] == 'create':
                button = ('do_create_picking', 'Create Picking')
            elif context['step'] == 'validate':
                button = ('do_validate_picking', 'Validate Picking')
        # ppl, two wizard steps
        elif picking_subtype == 'ppl':
            if context['step'] == 'moves':
                button = ('do_ppl1', 'Next')
            if context['step'] == 'pack_families':
                button = ('do_ppl2', 'Validate PPL')
                
        _moves_arch_lst += """
                <separator string="" colspan="4" />
                <label string="" colspan="2"/>
                <group col="2" colspan="2">
                <button icon='gtk-cancel' special="cancel"
                    string="_Cancel" />
                <button name="%s" string="%s"
                    colspan="1" type="object" icon="gtk-go-forward" />
            </group>
        </form>"""%button
        
        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result

    def __create_partial_picking_memory(self, move):
        move_memory = {
            'product_id' : move.product_id.id, 
            'quantity' : move.product_qty, 
            'product_uom' : move.product_uom.id, 
            'prodlot_id' : move.prodlot_id.id, 
            'move_id' : move.id,
            'asset_id': move.asset_id.id,
        }
    
        return move_memory
        
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
        # qty
        if not all([move.quantity > 0 for move in partial.product_moves_picking]):
            raise osv.except_osv(_('Error!'),  _('Selected quantity must be positive or equal to zero.'))
        
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
            partial_datas.setdefault(move.move_id.id, []).append({'product_id': move.product_id.id,
                                                                   'product_qty': move.quantity,
                                                                   'product_uom': move.product_uom.id,
                                                                   'prodlot_id': move.prodlot_id.id,
                                                                   'asset_id': move.asset_id.id,
                                                                   })
    
        # create the new picking object
        # TODO origin is not copied if name is not supplied as default.
        #      create a new sequence for each draft picking ticket, and bricoler with draft ref or something for traceability
        new_pick_id = pick_obj.copy(cr, uid, picking_id, {'move_lines': []}, context=context)
        pick_obj.write(cr, uid, [new_pick_id], {'origin': pick.origin, 'backorder_id': picking_id}, context=context)
        # create stock moves corresponding to partial datas
        # browse returns a list of browse object in the same order as move_ids
        # for now, each new line from the wizard corresponds to a new stock.move
        # it could be interesting to regroup according to production lot/asset id
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
                                                         'asset_id': partial['asset_id']}, context=context)
            # decrement the initial move, cannot be less than zero
            initial_qty = max(initial_qty - count, 0)
            move_obj.write(cr, uid, [move], {'product_qty': initial_qty}, context=context)
            
        # confirm the new picking ticket
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', new_pick_id, 'button_confirm', cr)
        
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
        # quantity check
        if not all([move.quantity >= 0 for move in partial.product_moves_picking]):
            raise osv.except_osv(_('Error!'),  _('Selected quantity must be positive or equal to zero.'))
        
        # data container
        # date of the picking ticket creation, not used for now
            #partial_datas = {
            #                 'delivery_date' : partial.date
            #}
        partial_datas = {}
        
        # picking ids
        picking_ids = context['active_ids']
        for picking_id in picking_ids:
            # for each picking
            partial_datas[picking_id] = {}
            pick = pick_obj.browse(cr, uid, picking_id, context=context)
            # out moves for delivery
            memory_moves_list = partial.product_moves_picking
            # organize data according to move id
            for move in memory_moves_list:
                partial_datas[picking_id].setdefault(move.move_id.id, []).append({'product_id': move.product_id.id,
                                                                       'product_qty': move.quantity,
                                                                       'product_uom': move.product_uom.id,
                                                                       'prodlot_id': move.prodlot_id.id,
                                                                       'asset_id': move.asset_id.id,
                                                                       })
            
            # create stock moves corresponding to partial datas
            # browse returns a list of browse object in the same order as move_ids
            move_ids = partial_datas[picking_id].keys()
            browse_moves = move_obj.browse(cr, uid, move_ids, context=context)
            moves = dict(zip(move_ids, browse_moves))
            
            for move in partial_datas[picking_id]:
                # qty selected
                count = 0
                # flag to update the first move
                first = True
                # initial qty
                initial_qty = moves[move].product_qty
                for partial in partial_datas[picking_id][move]:
                    # integrity check
                    partial['product_id'] == moves[move].product_id.id
                    partial['product_uom'] == moves[move].product_uom.id
                    # the quantity
                    count = count + partial['product_qty']
                    if first:
                        first = False
                        # update existing move
                        move_obj.write(cr, uid, move, {'product_qty': partial['product_qty'],
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
                    original_move = move_obj.search(cr, uid, [('picking_id', '=', backorder_id),
                                                              ('product_id', '=', moves[move].product_id.id),
                                                              ('product_uom', '=', moves[move].product_uom.id)])
                    assert original_move, 'No corresponding stock_move have been found in draft picking ticket for product %s and UOM %s'%(moves[move].product_id.name, moves[move].product_uom.name)
                    backorder_qty = move_obj.read(cr, uid, original_move, ['product_qty'], context=context)[0]['product_qty']
                    backorder_qty = max(backorder_qty + diff_qty, 0)
                    move_obj.write(cr, uid, original_move[0], {'product_qty': backorder_qty}, context=context)
        
            # create the new ppl object
            new_ppl_id = pick_obj.copy(cr, uid, pick.id, {'subtype': 'ppl'}, context=context)
            pick_obj.write(cr, uid, [new_ppl_id], {'origin': pick.origin, 'backorder_id': pick.id}, context=context)
            new_ppl = pick_obj.browse(cr, uid, new_ppl_id, context=context)
            # update locations of stock moves
            for move in pick_obj.browse(cr, uid, new_ppl_id, context=context).move_lines:
                move.write({'location_id': new_ppl.sale_id.shop_id.warehouse_id.lot_packing_id.id,
                            'location_dest_id': new_ppl.sale_id.shop_id.warehouse_id.lot_dispatch_id.id,
                            'previous_step_id': pick.id}, context=context)
            
            wf_service.trg_validate(uid, 'stock.picking', new_ppl_id, 'button_confirm', cr)
            # simulate check assign button, as stock move must be available
            new_ppl.action_assign()
            # trigger standard workflow
            pick_obj.action_move(cr, uid, [pick.id])
            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
        
        # close wizard
        return {'type': 'ir.actions.act_window_close'}
        
    def do_ppl(self, cr, uid, ids, context=None):
        '''
        
        '''
        stock_move_memory_ppl_tree_out

create_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
