
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
import datetime

class stock_partial_picking(osv.osv_memory):
    '''
    add message
    '''
    _inherit = "stock.partial.picking"
    
    def add_message(self, cr, uid, result, context=None):
        '''
        add message to arch
        '''
        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)
        message_in = '<label string="%s" colspan="4" />' % _('You receive %s products, please refer to the appropriate procedure.')
        message_out = '<label string="%s" colspan="4" />' % _('You ship %s products, please refer to the appropriate procedure and ensure that the mean of transport is appropriate.')
        button = '<button name="copy_all" string="%s" colspan="1" type="object" icon="gtk-jump-to"/>' % _('Copy all')
        button_2 = '<button name="uncopy_all" string="%s" colspan="1" type="object" icon="gtk-undo"/>' % _('Clear all')
        if not picking_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result
        
        type = False
        contains_kc = False
        contains_dg = False
        
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            type = pick.type
            for m in pick.move_lines:
                if m.product_id.heat_sensitive_item:
                    contains_kc = True
                if m.product_id.dangerous_goods:
                    contains_dg = True
            
        if contains_kc and contains_dg:
            fill = _('heat sensitive and dangerous goods')
        elif contains_kc:
            fill = _('heat sensitive')
        elif contains_dg:
            fill = _('dangerous goods')
        else:
            fill = ''
            
        message = message_out
        if type == 'in':
            message = message_in
        
        if fill:
            message = message%fill
        else:
            message = ''

        # add field in arch
        arch = result['arch']
        l = arch.split('<field name="date" invisible="1"/>')
        arch = l[0]
    
        if context.get('step',False) not in ['create','validate','returnproducts','ppl2','ppl1']:
            arch += button
            arch += button_2
        arch += '<field name="date" invisible="1"/>' + message + l[1]
        result['arch'] = arch
        
        return result

    def copy_all(self, cr, uid, ids, context=None):
        partial = self.browse(cr, uid, ids[0], context=context)

        for move in partial.product_moves_out:
            self.pool.get('stock.move.memory.out').write(cr,uid, [move.id], { 'quantity' : move.ordered_quantity } )
        for move in partial.product_moves_in:
            self.pool.get('stock.move.memory.in').write(cr,uid, [move.id], { 'quantity' : move.ordered_quantity } )
        return {
            'name': context.get('wizard_name'),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': context['model'],
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context,
        }
        #return self.pool.get('wizard').open_wizard(cr, uid, [ids[0]], type='update', context=context)

    def uncopy_all(self, cr, uid, ids, context=None):
        partial = self.browse(cr, uid, ids[0], context=context)
        for move in partial.product_moves_out:
            self.pool.get('stock.move.memory.out').write(cr, uid, [move.id], {'quantity': 0.0})
        for move in partial.product_moves_in:
            self.pool.get('stock.move.memory.in').write(cr, uid, [move.id], {'quantity': 0.0})
        return {
            'name': context.get('wizard_name'),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': context['model'],
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context,
        }
        #return self.pool.get('wizard').open_wizard(cr, uid, [ids[0]], type='update', context=context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add message
        '''
        if context is None:
            context = {}
        
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        # add warning messages
        result = self.add_message(cr, uid, result, context=context)
        return result
    
    def __create_partial_picking_memory(self, move, pick_type):
        '''
        add the asset_id
        '''
        move_memory = super(stock_partial_picking, self).__create_partial_picking_memory(move, pick_type)
        assert move_memory is not None
        
        move_memory.update({'expiry_date': move.expired_date, 'ordered_quantity': move.product_qty, 'quantity': 0.0, 'uom_ordered': move.product_uom.id })
        
        return move_memory
    
    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_partial
        '''
        # call to super
        partial_datas = super(stock_partial_picking, self).do_partial_hook(cr, uid, context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing specific_rules > wizard > stock_partial_picking'
        prodlot_obj = self.pool.get('stock.production.lot')
        
        move = kwargs.get('move')
        assert move, 'move is missing'
        
        if move.batch_number_check and not move.prodlot_id:
            raise osv.except_osv(_('Error'), _('No Batch Number set for Batch Number mandatory product(s).'))
        if move.expiry_date_check and not move.expiry_date:
            raise osv.except_osv(_('Error'), _('No Expiry Date set for Expiry Date mandatory product(s).'))

        # if only expiry date mandatory, and not batch management
        if move.expiry_date_check and not move.batch_number_check:        
            # if no production lot
            if not move.prodlot_id:
                if move.expiry_date:
                    # if it's a incoming shipment
                    if move.type_check == 'in':
                        # double check to find the corresponding prodlot
                        prodlot_ids = prodlot_obj.search(cr, uid, [('life_date', '=', move.expiry_date),
                                                                    ('type', '=', 'internal'),
                                                                    ('product_id', '=', move.product_id.id)], context=context)
                        # no prodlot, create a new one
                        if not prodlot_ids:
                            vals = {'product_id': move.product_id.id,
                                    'life_date': move.expiry_date,
                                    #'name': datetime.datetime.strptime(move.expiry_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                                    'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial'),
                                    'type': 'internal',
                                    }
                            prodlot_id = prodlot_obj.create(cr, uid, vals, context)
                        else:
                            prodlot_id = prodlot_ids[0]
                        # assign the prod lot to partial_datas
                        partial_datas['move%s' % (move.move_id.id)].update({'prodlot_id': prodlot_id,})
                    else:
                        # should not be reached thanks to UI checks
                        raise osv.except_osv(_('Error !'), _('No Batch Number with Expiry Date for Expiry Date Mandatory and not Incoming Shipment should not happen. Please hold...'))
        
        return partial_datas

stock_partial_picking()
