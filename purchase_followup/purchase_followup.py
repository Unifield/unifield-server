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

from osv import osv
from osv import fields

from tools.translate import _


class purchase_order_followup(osv.osv_memory):
    _name = 'purchase.order.followup'
    _description = 'Purchase Order Followup'
    
    def _shipped_rate(self, cr, uid, line, context={}):
        '''
        Return the shipped rate of a PO line
        '''
        line_value = line.price_subtotal
        move_value = 0.00
        for move in line.move_ids:
            if move.state == 'done':
                move_value += move.product_qty*move.price_unit
            
        return round((move_value/line_value)*100, 2)
    
    def _get_move_state(self, cr, uid, move_state, context={}):
        move_obj = self.pool.get('stock.move')
        sel = move_obj.fields_get(cr, uid, ['state'])
        res = dict(sel['state']['selection']).get(move_state)
        tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', 'stock.move,state'), ('src', '=', res)])
        if tr_ids:
            return self.pool.get('ir.translation').read(cr, uid, tr_ids, ['value'])[0]['value']
        else:
            return res
        
    def update_view(self, cr, uid, ids, context={}):
        '''
        Reload the view
        '''
        if ids:
            order_id = self.browse(cr, uid, ids, context=context)[0].order_id.id
        else:
            raise osv.except_osv(_('Error'), _('Order followup not found !'))
        
        self.unlink(cr, uid, ids, context=context)
        
        context.update({'active_id': order_id, 'active_ids': [order_id], 'update': True})
        
        return self.start_order_followup(cr, uid, ids, context)
    
    def close_view(self, cr, uid, ids, context={}):
        '''
        Close the view
        '''
        return {'type': 'ir.actions.act_window_close'}
    
    def start_order_followup(self, cr, uid, ids, context={}):
        # openERP BUG ?
        ids = context.get('active_ids',[])
        
        if not ids:
            raise osv.except_osv(_('Error'), _('No order found !'))
        if len(ids) != 1:
            raise osv.except_osv(_('Error'), _('You should select one order to follow !'))
        
        order_obj = self.pool.get('purchase.order')
        line_obj = self.pool.get('purchase.order.followup.line')
        
        for order in order_obj.browse(cr, uid, ids, context=context):
            if order.state not in ('approved', 'done', 'shipping_exception', 'invoice_exception'):
                raise osv.except_osv(_('Error'), _('You cannot follow a non-confirmed Purchase order !'))
            
            followup_id = self.create(cr, uid, {'order_id': order.id}, context=context)
            
            for line in order.order_line:
                first_move = True
                for move in line.move_ids:
                    line_data = {'followup_id': followup_id,
                                 'move_id': move.id,
                                 'line_id': line.id,
                                 'picking_id': move.picking_id.id,
                                 'move_state': self._get_move_state(cr, uid, move.state, context=context),
                                 'line_name': line.line_number,
                                 'line_product_id': first_move and line.product_id.id or False,
                                 'line_product_qty': first_move and line.product_qty or False,
                                 'line_uom_id': first_move and line.product_uom.id or False,
                                 'line_confirmed_date': first_move and line.confirmed_delivery_date or False,
                                 'line_shipped_rate': first_move and self._shipped_rate(cr, uid, line, context) or "no-progressbar",
                                 'move_product_id': line.product_id.id != move.product_id.id and move.product_id.id or False,
                                 'move_product_qty': line.product_qty != move.product_qty and '%.2f' % move.product_qty or '',
                                 'move_uom_id': line.product_uom.id != move.product_uom.id and move.product_uom.id or False,
                                 'move_delivery_date': line.confirmed_delivery_date != move.date_expected and move.date_expected or False,
                                 }
                    
                    line_obj.create(cr, uid, line_data, context=context)
                    
                    # Unflag the first move
                    if first_move:
                        first_move = False
                        
        res = {'type': 'ir.actions.act_window',
                       'res_model': 'purchase.order.followup',
                       'view_type': 'form',
                       'view_mode': 'form',
                       'res_id': followup_id,
                       'context': context,}
        
        # If update the view, return the view in the same screen
        if context.get('update'):
            res.update({'target': 'dummy'})
            
        return res
    
    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order reference', readonly=True),
        'supplier_ref': fields.related('order_id', 'partner_ref', string='Supplier Reference', readonly=True, type='char'),
        'delivery_requested_date': fields.related('order_id', 'delivery_requested_date', string='Delivery requested date', type='date', readonly=True),
        'delivery_confirmed_date': fields.related('order_id', 'delivery_confirmed_date', string='Delivery confirmed date', type='date', readonly=True),
        'line_ids': fields.one2many('purchase.order.followup.line', 'followup_id', readonly=True),
        
    }
    
purchase_order_followup()

class purchase_order_followup_line(osv.osv_memory):
    _name = 'purchase.order.followup.line'
    _description = 'Purchase Order Followup Line'
    _rec_name = 'move_id'
    
    _columns = {
        'move_id': fields.many2one('stock.move', string='Move'),
        'line_id': fields.many2one('purchase.order.line', string='Order line'),
        'followup_id': fields.many2one('purchase.order.followup', string='Follow-up'),
        'line_name': fields.char(size=64, string='#'),
        'line_product_id': fields.many2one('product.product', string='Product'),
        'line_product_qty': fields.char(size=64, string='Qty'),
        'line_uom_id': fields.many2one('product.uom', string='UoM'),
        'line_confirmed_date': fields.date(string='Del. Conf. date'),
        'line_shipped_rate': fields.float(digits=(16,2), string='% of line received'),
        'picking_id': fields.many2one('stock.picking', string='Incoming shipment'),
        'move_product_id': fields.many2one('product.product', string='New product'),
        'move_product_qty': fields.char(size=64, string='New Qty'),
        'move_uom_id': fields.many2one('product.uom', string='New UoM'),
        'move_delivery_date': fields.date(string='New Del. date'),
        'move_state': fields.char(size=64, string='State'),
    }
    
purchase_order_followup_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: