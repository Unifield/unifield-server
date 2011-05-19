#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

from osv import osv, fields
from tools.translate import _

class picking_create_picking_ticket(osv.osv_memory):
    _name = 'picking.create.picking.ticket'
    _description = 'Create Picking Ticket'
    
    
    _columns = {
                'delivery_orders': fields.many2many('stock.picking', 'create_picking_ticket_stock_picking', 'wizard_id', 'stock_picking_id', 'Delivery Orders'),
    }

    _defaults = {
    }

    def view_init(self, cr , uid , fields_list, context=None):
        '''
        http://doc.openerp.com/v6.0/developer/2_5_Objects_Fields_Methods/methods.html#osv.osv.osv.view_init
        
        Override this method to do specific things when a view on the object is opened.
        '''
        pass
    
            
    def onChangeDeliveryOrders(self, cr, uid, ids, deliveryOrders, context=None):
        '''
        onChange function for delivery_orders
        '''
        return {}
        

    def createPickingTickets(self, cr, uid, ids, context=None):
        '''
        generate picking tickets and picking ticket lines
        '''
        
        # find the sequence, create if needed
        seq_pool = self.pool.get('ir.sequence').get(cr, uid, 'picking.ticket')
        
        # data from view
        data = self.read(cr, uid, ids)
        
        # create the picking tickets - delivery orders are of type stock.picking
        selectedIds = data[0]['delivery_orders']
        
        for doId in selectedIds:
            # corresponding object
            deliveryOrder = self.pool.get('stock.picking').browse(cr, uid, doId, context=context)
            soId = deliveryOrder.sale_id.id
            saleOrder = self.pool.get('sale.order').browse(cr, uid, soId, context=context)
            # create a picking_ticket
            values = {
                      'name': saleOrder.name,
                      'stock_picking_id': deliveryOrder.id,
                      'sale_order_id': saleOrder.id,
                      'state': 'created',
                      }
            pickingTicketId = self.pool.get('picking.ticket').create(cr, uid, values)
            # for each stock move, we create the corresponding picking ticket line
            pickingTicketLineList = []
            for smId in deliveryOrder.move_lines:
                # corresponding object
                sm = self.pool.get('stock.move').browse(cr, uid, smId.id, context=context)
                solId = sm.sale_line_id.id
                sol = self.pool.get('sale.order.line').browse(cr, uid, solId, context=context)
                # create a picking ticket line
                values = {
                          'name': 'picking line',
                          'picking_ticket_id': pickingTicketId,
                          'stock_move_id': smId.id,
                          'sale_order_line_id': solId,
                          }
                pickingTicketLineId = self.pool.get('picking.ticket.line').create(cr, uid, values)          
        
        # action to be returned
#        mod_obj = self.pool.get('ir.model.data')
#        act_obj = self.pool.get('ir.actions.act_window')
#        result = mod_obj.get_object_reference(cr, uid, 'picking', 'picking_ticket_action')
#        
#        id = result and result[1] or False
#        result = act_obj.read(cr, uid, [id], context=context)
#        result = result[0]
         
        return {'type': 'ir.actions.act_window_close'}


picking_create_picking_ticket()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: