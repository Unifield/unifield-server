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


##############################################################################
#
#    This class is a common place for special treatment for Remote Warehouse
#
##############################################################################

from osv import fields, osv
from tools.translate import _

'''
 This class extension is to treat special cases for remote warehouse
'''
class stock_move(osv.osv):
    # This is to treat the location requestor on Remote warehouse instance if IN comes from an IR
    _inherit = 'stock.move'
    _columns = {'location_requestor_rw': fields.integer(string='Location Requestor For RW-IR'),
                }
    _defaults = {
        'location_requestor_rw': -1,
    }

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}
        if not vals:
            vals = {}

        # Save the location requestor from IR into the field location_requestor_rw if exists
        res = super(stock_move, self).create(cr, uid, vals, context=context)
        move = self.browse(cr, uid, [res], context=context)[0]
        if move.purchase_line_id:
            proc = move.purchase_line_id.procurement_id
            if proc and proc.sale_order_line_ids and proc.sale_order_line_ids[0].order_id and proc.sale_order_line_ids[0].order_id.procurement_request:
                location_dest_id = proc.sale_order_line_ids[0].order_id.location_requestor_id.id
                cr.execute('update stock_move set location_requestor_rw=%s where id=%s', (location_dest_id, move.id))
        
        return res

    def _get_location_for_internal_request(self, cr, uid, context=None, **kwargs):
        '''
            If it is a remote warehouse instance, then take the location requestor from IR
        '''
        location_dest_id = super(stock_move, self)._get_location_for_internal_request(cr, uid, context=context, **kwargs)
        type = self.pool.get('sync.client.entity').get_entity(cr, uid).usb_instance_type
        if type == 'remote_warehouse':
            move = kwargs['move']
            if move.location_requestor_rw != -1:
                return move.location_requestor_rw
        # for any case, just return False and let the caller to pick the normal loc requestor
        return False

stock_move()

class stock_picking(osv.osv):
    '''
    Stock.picking override for Remote Warehouse tasks
    '''
    _inherit = "stock.picking"

    def _hook_check_cp_instance(self, cr, uid, ids, context=None):
        res = super(stock_picking, self)._hook_check_cp_instance(cr, uid, ids, context=context)
        rw_type = self.pool.get('sync.client.entity').get_entity(cr, uid).usb_instance_type
        if rw_type == 'central_platform':
            name = "This action should only be performed at the Remote Warehouse instance! Are you sure to proceed it at this main instance?"
            model = 'confirm'
            step = 'default'
            question = name
            clazz = 'stock.picking'
            func = 'original_action_process'
            args = [ids]
            kwargs = {}            
            wiz_obj = self.pool.get('wizard')
            # open the selected wizard
            res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context, question=question,
                                                                                                    callback={'clazz': clazz,
                                                                                                              'func': func,
                                                                                                              'args': args,
                                                                                                              'kwargs': kwargs}))
            return res
        return False            

stock_picking()
