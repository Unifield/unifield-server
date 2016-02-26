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

from osv import fields, osv
from tools.translate import _
import time

class stock_partial_picking(osv.osv_memory):
    _inherit = "stock.partial.picking"
    _description = "Partial Picking with hook"


    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>wizard>stock_partial_picking.py>stock_partial_picking

        - allow to modify partial_datas
        '''
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'partial_datas missing stock_override > wizard > stock_partial_picking'

        return partial_datas

    def return_hook_do_partial(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>wizard>stock_partial_picking.py>stock_partial_picking

        - allow to modify returned value from button method
        '''
        return {'type': 'ir.actions.act_window_close'}

    def _hook_default_get(self, cr, uid, picking_ids, context=None):
        result = []
        pick_obj = self.pool.get('stock.picking')
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            pick_type = self.get_picking_type(cr, uid, pick, context=context)
            for m in pick.move_lines:
                if m.state in ('done', 'cancel', 'confirmed') or  m.product_qty == 0.00 :
                    continue
                result.append(self.__create_partial_picking_memory(m, pick_type))
        return result

    # @@@override stock>wizard>stock_partial_picking.py>stock_partial_picking
    def do_partial(self, cr, uid, ids, context=None):
        """ Makes partial moves and pickings done.
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param fields: List of fields for which we want default values
        @param context: A standard dictionary
        @return: A dictionary which of fields with values.
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        pick_obj = self.pool.get('stock.picking')
        uom_obj = self.pool.get('product.uom')
        prodlot_obj = self.pool.get('stock.production.lot')

        # save the wizard ids into context - for compatibility with cross_docking assertion on wizard_ids
        if 'wizard_ids' not in context:
            context.update(wizard_ids=ids)

        picking_ids = context.get('active_ids', False)
        partial = self.browse(cr, uid, ids[0], context=context)
        partial_datas = {
            'delivery_date' : partial.date
        }

        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            total_qty = 0.00
            picking_type = self.get_picking_type(cr, uid, pick, context=context)
            moves_list = picking_type == 'in' and partial.product_moves_in or partial.product_moves_out

            prodlot_integrity = {}

            # integrity constraint
            integrity_check = self.integrity_check_do_incoming_shipment(cr, uid, ids, picking_type, None, context=context)
            if not integrity_check:
                # the windows must be updated to trigger tree colors
                return self.pool.get('wizard').open_wizard(cr, uid, picking_ids, w_type='update', context=context)

            if not moves_list:
                    raise osv.except_osv(_('Warning !'), _('Selected list to process cannot be empty.'))

            for move in moves_list:
                # Adding a check whether any line has been added with new qty
                if not move.move_id:
                    raise osv.except_osv(_('Processing Error'), \
                    _('You cannot add any new move while validating the picking, rather you can split the lines prior to validation!'))

                calc_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, \
                                    move.quantity, move.move_id.product_uom.id)

                # Add a check on prodlot quantity
                if picking_type != 'in' and move.prodlot_id:
                    if move.prodlot_id.id not in prodlot_integrity:
                        prodlot_integrity.update({move.prodlot_id.id: {}})

                    if move.location_id.id not in prodlot_integrity[move.prodlot_id.id]:
                        prodlot_integrity[move.prodlot_id.id].update({move.location_id.id: 0.00})

                    prodlot_integrity[move.prodlot_id.id][move.location_id.id] += calc_qty

                    prodlot_qty = prodlot_obj.browse(cr, uid, move.prodlot_id.id, context={'location_id': move.location_id.id}).stock_available
                    if prodlot_qty < calc_qty:
                        raise osv.except_osv(_('Processing Error'), \
                        _('Processing quantity %d %s for %s is larger than the available quantity in Batch Number %s (%d) !')\
                        % (move.quantity, move.product_uom.name, move.product_id.name, \
                        move.prodlot_id.name, prodlot_qty))

                # Adding a check whether any move line contains exceeding qty to original moveline
                if calc_qty > move.move_id.product_qty:
                    raise osv.except_osv(_('Processing Error'),
                    _('Processing quantity %d %s for %s is larger than the available quantity %d %s !')\
                    % (move.quantity, move.product_uom.name, move.product_id.name, \
                      move.move_id.product_qty, move.move_id.product_uom.name))

                total_qty += calc_qty

                # Adding a check whether any move line contains qty less than zero
                if calc_qty <= 0:
                    # if no quantity, don't process the move
                    continue
                    raise osv.except_osv(_('Processing Error'), \
                            _('Can not process empty lines !'))

                if partial_datas.has_key('move%s' % (move.move_id.id)) and move.quantity > 0:
                    new_move_id = self.pool.get('stock.move').copy(cr, uid, move.move_id.id, {'product_qty': calc_qty, 'state':'assigned', 'line_number':move.line_number  })
                    old_move_id = self.pool.get('stock.move').browse(cr, uid, move.move_id.id)
                    self.pool.get('stock.move').write(cr, uid, [move.move_id.id], {'product_qty':old_move_id.product_qty - calc_qty })
                    new_move = self.pool.get('stock.move').browse(cr, uid, new_move_id)
                    partial_datas['move%s' % (new_move_id)] = {
                        'product_id': move.product_id.id,
                        'product_qty': calc_qty,
                        'product_uom': move.move_id.product_uom.id,
                        'prodlot_id': move.prodlot_id.id,
                    }

                else:
                    partial_datas['move%s' % (move.move_id.id)] = {
                        'product_id': move.product_id.id,
                        'product_qty': calc_qty,
                        'product_uom': move.move_id.product_uom.id,
                        'prodlot_id': move.prodlot_id.id,
                    }

                if (picking_type == 'in') and (move.product_id.cost_method == 'average') and not move.move_id.location_dest_id.cross_docking_location_ok:
                    partial_datas['move%s' % (move.move_id.id)].update({
                                                    'product_price' : move.cost,
                                                    'product_currency': move.currency.id,
                                                    })

                # override : add hook call
                partial_datas = self.do_partial_hook(cr, uid, context=context, move=move, partial_datas=partial_datas, pick=pick, partial=partial)

            # Check prodlot qty integrity
            for prodlot in prodlot_integrity:
                for location in prodlot_integrity[prodlot]:
                    tmp_prodlot = prodlot_obj.browse(cr, uid, prodlot, context={'location_id': location})
                    prodlot_qty = tmp_prodlot.stock_available
                    if prodlot_qty < prodlot_integrity[prodlot][location]:
                        raise osv.except_osv(_('Processing Error'), \
                        _('Processing quantity %d for %s is larger than the available quantity in Batch Number %s (%d) !')\
                        % (prodlot_integrity[prodlot][location], tmp_prodlot.product_id.name, tmp_prodlot.name, \
                        prodlot_qty))

            if not total_qty:
                raise osv.except_osv(_('Processing Error'), _('No quantity to process, please fill quantity to process before processing the moves'))

        res = pick_obj.do_partial(cr, uid, picking_ids, partial_datas, context=context)
        return self.return_hook_do_partial(cr, uid, context=context, partial_datas=partial_datas, res=res)
    #@@@override end


stock_partial_picking()
