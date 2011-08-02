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

from osv import osv, fields

class sale_order_followup(osv.osv_memory):
    _name = 'sale.order.followup'
    _description = 'Sales Order Followup'
    
    def get_selection(self, cr, uid, o, field):
        """
        Retourne le libellé d'un champ sélection
        """
        sel = self.pool.get(o._name).fields_get(cr, uid, [field])
        res = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
        name = '%s,%s' % (o._name, field)
        tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', res)])
        if tr_ids:
            return self.pool.get('ir.translation').read(cr, uid, tr_ids, ['value'])[0]['value']
        else:
            return res
    
    def _get_order_state(self, cr, uid, ids, field_name, args, context={}):
        if not context:
            context = {}
            
        res = {}
            
        for follow in self.browse(cr, uid, ids, context=context):
            res[follow.id] = None
            
            if follow.order_id:
                res[follow.id] = self.get_selection(cr, uid, follow.order_id, 'state')
            
        return res
    
    _columns = {
        'order_id': fields.many2one('sale.order', string='Internal reference', readonly=True),
        'cust_ref': fields.related('order_id', 'client_order_ref', string='Customer reference', readonly=True, type='char'),
        'creation_date': fields.related('order_id', 'create_date', string='Creation date', readonly=True, type='date'),
        'state': fields.function(_get_order_state, method=True, type='char', string='Order state', readonly=True),
        'requested_date': fields.related('order_id', 'delivery_requested_date', string='Requested date', readonly=True, type='date'),
        'confirmed_date': fields.related('order_id', 'delivery_confirmed_date', string='Confirmed date', readonly=True, type='date'),
        'line_ids': fields.one2many('sale.order.line.followup', 'followup_id', string='Lines', readonly=True),
    }
    
    def start_order_followup(self, cr, uid, ids, context={}):
        order_obj = self.pool.get('sale.order')
        order_line_obj = self.pool.get('sale.order.line')
        line_obj = self.pool.get('sale.order.line.followup')
        
        # openERP BUG ?
        ids = context.get('active_ids',[])
        
        if not ids:
            raise osv.except_osv(_('Error'), _('No order found !'))
        if len(ids) != 1:
            raise osv.except_osv(_('Error'), _('You should select one order to follow !'))
        
        followup_id = False
        
        for o in order_obj.browse(cr, uid, ids, context=context):
            followup_id = self.create(cr, uid, {'order_id': o.id})
            
            for line in o.order_line:
                purchase_ids = self.get_purchase_ids(cr, uid, line.id, context=context)
                incoming_ids = self.get_incoming_ids(cr, uid, line.id, purchase_ids, context=context)
                outgoing_ids = self.get_outgoing_ids(cr, uid, line.id, context=context)
                tender_ids = self.get_tender_ids(cr, uid, line.id, context=context)
                quotation_ids = self.get_quotation_ids(cr, uid, line.id, context=context)
                
                line_obj.create(cr, uid, {'followup_id': followup_id,
                                          'line_id': line.id,
#                                          'tender_ids': [(6,0,tender_ids)],
                                          'quotation_ids': [(6,0,quotation_ids)],
                                          'purchase_ids': [(6,0,purchase_ids)],
                                          'incoming_ids': [(6,0,incoming_ids)],
                                          'outgoing_ids': [(6,0,outgoing_ids)],})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order.followup',
                'res_id': followup_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new'}
        
    def get_purchase_ids(self, cr, uid, line_id, context={}):
        '''
        Returns a list of purchase orders related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')
        
        if isinstance(line_id, (int, long)):
            line_id = [line_id]
            
        purchase_ids = []
        
        for line in line_obj.browse(cr, uid, line_id, context=context):
            if line.type == 'make_to_order' and line.procurement_id \
            and line.procurement_id.purchase_id and line.procurement_id.purchase_id.id \
            and line.procurement_id.purchase_id.state != 'draft':
                purchase_ids.append(line.procurement_id.purchase_id.id)
        
        return purchase_ids
    
    def get_quotation_ids(self, cr, uid, line_id, context={}):
        '''
        Returns a list of request for quotation related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')
        
        if isinstance(line_id, (int, long)):
            line_id = [line_id]
            
        quotation_ids = []
        
        for line in line_obj.browse(cr, uid, line_id, context=context):
            if line.type == 'make_to_order' and line.procurement_id \
            and line.procurement_id.purchase_id and line.procurement_id.purchase_id.id \
            and line.procurement_id.purchase_id.state == 'draft':
                quotation_ids.append(line.procurement_id.purchase_id.id)
        
        return quotation_ids
        
    def get_incoming_ids(self, cr, uid, line_id, purchase_ids, context={}):
        '''
        Returns a list of incoming shipments related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')
        purchase_obj = self.pool.get('purchase.order')
                
        if isinstance(line_id, (int, long)):
            line_id = [line_id]
            
        if isinstance(purchase_ids, (int, long)):
            purchase_ids= [purchase_ids]
            
        incoming_ids = []
        
        for line in line_obj.browse(cr, uid, line_id, context=context):
            for po in purchase_obj.browse(cr, uid, purchase_ids, context=context):
                for po_line in po.order_line:
                    if po_line.product_id.id == line.product_id.id:
                        for move in po_line.move_ids:
                            incoming_ids.append(move.id)
        
        return incoming_ids
        
    def get_outgoing_ids(self, cr, uid, line_id, context={}):
        '''
        Returns a list of outgoing deliveries related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')
                
        if isinstance(line_id, (int, long)):
            line_id = [line_id]
            
        outgoing_ids = []
        
        for line in line_obj.browse(cr, uid, line_id, context=context):
            for move in line.move_ids:
                outgoing_ids.append(move.id)
        
        return outgoing_ids
    
    def get_tender_ids(self, cr, uid, line_id, context={}):
        '''
        Returns a list of call for tender related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')
                
        if isinstance(line_id, (int, long)):
            line_id = [line_id]
            
        tender_ids = []
        
        for line in line_obj.browse(cr, uid, line_id, context=context):
            pass
        
        return tender_ids
        
    
sale_order_followup()

class sale_order_line_followup(osv.osv_memory):
    _name = 'sale.order.line.followup'
    _description = 'Sales Order Lines Followup'
    
    _columns = {
        'followup_id': fields.many2one('sale.order.followup', string='Sale Order Followup', required=True),
        'line_id': fields.many2one('sale.order.line', string='Order line', required=True, readonly=True),
        'line_number': fields.related('line_id', 'line_number', string='Order line', readonly=True, type='integer'),
        'product_id': fields.related('line_id', 'product_id', string='Product reference', readondy=True, 
                                     type='many2one', relation='product.product'),
        'qty_ordered': fields.related('line_id', 'product_uom_qty', string='Ordered qty', readonly=True),
        #TODO: Add call for tender when the feature of call for tender will be implemented
#        'tender_ids': fields.many2many('call.tender', 'call_tender_follow_rel',
#                                       'follow_line_id', 'tender_id', string='Call for tender'),
        'quotation_ids': fields.many2many('purchase.order', 'quotation_follow_rel', 'follow_line_id',
                                          'quotation_id', string='Requests for Quotation', readonly=True),
        'purchase_ids': fields.many2many('purchase.order', 'purchase_follow_rel', 'follow_line_id', 
                                         'purchase_id', string='Purchase Orders', readonly=True),
        'incoming_ids': fields.many2many('stock.picking', 'incoming_follow_rel', 'follow_line_id', 
                                         'incoming_id', string='Incoming Shipment', readonly=True),
        'outgoing_ids': fields.many2many('stock.picking', 'outgoing_follow_rel', 'follow_line_id',
                                         'outgoing_id', string='Outgoing Deliveries', readonly=True),
        
        
    }
    
sale_order_line_followup()