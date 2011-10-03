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
from tools.translate import _

class sale_order_followup(osv.osv_memory):
    _name = 'sale.order.followup'
    _description = 'Sales Order Followup'
    
    def get_selection(self, cr, uid, o, field):
        """
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
        'choose_type': fields.selection([('documents', 'Documents view'), ('progress', 'Progress view')], string='Type of view'),
    }
    
    _defaults = {
        'choose_type': lambda *a: 'documents',
    }
    
    def go_to_view(self, cr, uid, ids, context={}):
        '''
        Launches the correct view according to the user's choice
        '''
        for followup in self.browse(cr, uid, ids, context=context):
            if followup.choose_type == 'documents':
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_followup_document_view')[1]
            else:
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_followup_progress_view')[1]
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order.followup',
                'res_id': followup.id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new'}
        
    def switch_documents(self, cr, uid, ids, context={}):
        '''
        Switch to documents view
        '''
        self.write(cr, uid, ids, {'choose_type': 'documents'})
        
        return self.go_to_view(cr, uid, ids, context=context)
    
    def switch_progress(self, cr, uid, ids, context={}):
        '''
        Switch to progress view
        '''
        self.write(cr, uid, ids, {'choose_type': 'progress'})
        
        return self.go_to_view(cr, uid, ids, context=context)
    
    def start_order_followup(self, cr, uid, ids, context={}):
        order_obj = self.pool.get('sale.order')
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
                                          'tender_ids': [(6,0,tender_ids)],
                                          'quotation_ids': [(6,0,quotation_ids)],
                                          'purchase_ids': [(6,0,purchase_ids)],
                                          'incoming_ids': [(6,0,incoming_ids)],
                                          'outgoing_ids': [(6,0,outgoing_ids)],})
                    
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_line_follow_choose_view')[1]

        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order.followup',
                'res_id': followup_id,
                'view_id': [view_id],
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
            if line.type == 'make_to_order' and line.procurement_id:
                if line.procurement_id.purchase_id and line.procurement_id.purchase_id.state not in ('draft', 'rfq_done'):
                    purchase_ids.append(line.procurement_id.purchase_id.id)
                elif line.procurement_id.tender_id and line.procurement_id.tender_id.rfq_ids:
                    for rfq in line.procurement_id.tender_id.rfq_ids:
                        if rfq.state not in ('draft', 'rfq_done'):
                            purchase_ids.append(rfq.id)
        
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
            if line.type == 'make_to_order' and line.procurement_id:
                if line.procurement_id.purchase_id and line.procurement_id.purchase_id.state in ('draft', 'rfq_done'):
                    quotation_ids.append(line.procurement_id.purchase_id.id)
                elif line.procurement_id.tender_id and line.procurement_id.tender_id.rfq_ids:
                    for rfq in line.procurement_id.tender_id.rfq_ids:
                        if rfq.state in ('draft', 'rfq_done', 'rfq_updated', 'rfq_sent'):
                            quotation_ids.append(rfq.id)
                
        
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
            for tender in line.tender_line_ids:
                tender_ids.append(tender.tender_id.id)
        
        return tender_ids
        
    
sale_order_followup()

class sale_order_line_followup(osv.osv_memory):
    _name = 'sale.order.line.followup'
    _description = 'Sales Order Lines Followup'
    
    def _get_status(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Get all status about the line
        '''
        move_obj = self.pool.get('stock.move')
        
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'sourced_ok': 'Waiting',
                            'quotation_status': 'No quotation',
                            'tender_status': 'N/A',
                            'purchase_status': 'No order',
                            'incoming_status': 'No shipment',
                            'outgoing_status': 'No deliveries',
                            'product_available': 'Waiting',
                            'available_qty': 0.00}
            
            if line.line_id.state == 'draft':
                res[line.id]['sourced_ok'] = 'No'
            if line.line_id.state in ('confirmed', 'done'):
                res[line.id]['sourced_ok'] = 'Done'
            if line.line_id.state == 'cancel':
                res[line.id]['sourced_ok'] = 'Cancelled'
            if line.line_id.state == 'exception':
                res[line.id]['sourced_ok'] = 'Exception'
            
            # Get information about the availability of the product
            move_ids = move_obj.search(cr, uid, [('sale_line_id', '=', line.line_id.id)])
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                # Change the state to Done only when all stock moves are done
                if move.state in ('assigned', 'done'):
                    res[line.id]['available_qty'] += move.product_qty
                    if res[line.id]['product_available'] == 'Waiting':
                        res[line.id]['product_available'] = 'Done'
                # If at least one stock move is not done, change the state to 'In Progress'
                if move.state in ('draft', 'confirmed') and res[line.id]['product_available'] == 'Done':
                    res[line.id]['product_available'] = 'In Progress'
                # If at least one stock move was cancelled, the state is Exception
                # TODO : See with Magali if we need to take care about cancelled associated stock moves
                if move.state == 'cancel':
                    res[line.id]['product_available'] = 'Exception'
            
            # Get information about the status of the RfQ
            for quotation in line.quotation_ids:
                if quotation.state == 'draft':
                    res[line.id]['quotation_status'] = 'Waiting'
                if quotation.state == 'rfq_sent' and res[line.id]['quotation_status'] not in ('Waiting'):
                    res[line.id]['quotation_status'] = 'Sent'
                elif quotation.state == 'rfq_updated' and res[line.id]['quotation_status'] not in ('Waiting', 'Sent'):
                    res[line.id]['quotation_status'] = 'Updated'
                if quotation.state == 'rfq_done' and res[line.id]['quotation_status'] not in ('Waiting', 'Sent', 'Updated'):
                    res[line.id]['quotation_status'] = 'Done'
                    
            # Get information about the state of all call for tender
            for tender in line.tender_ids:
                if tender.state == 'draft':
                    res[line.id]['tender_status'] = 'Waiting'
                elif tender.state == 'comparison' and res[line.id]['tender_status'] != 'Waiting':
                    res[line.id]['tender_status'] = 'In Progress'
                elif tender.state == 'done' and res[line.id]['tender_status'] not in ('Waiting', 'In Progress'):
                    res[line.id]['tender_status'] = 'Done'
                elif tender.state == 'cancel':
                    res[line.id]['tender_status'] = 'Exception'
            
            # Get information about the state of all purchase order
            if line.line_id.type == 'make_to_stock':
                res[line.id]['quotation_status'] = 'N/A'
                res[line.id]['purchase_status'] = 'N/A'
                res[line.id]['incoming_status'] = 'N/A'
                if line.line_id.product_id:
                    context.update({'shop_id': line.line_id.order_id.shop_id.id,
                                    'uom_id': line.line_id.product_uom.id})
                    res[line.id]['available_qty'] = self.pool.get('product.product').browse(cr, uid, line.line_id.product_id.id, context=context).qty_available

            for order in line.purchase_ids:
                if order.state in ('confirmed', 'wait'):
                    res[line.id]['purchase_status'] = 'Confirmed'
                if order.state == 'approved' and res[line.id]['purchase_status'] not in ('Confirmed', 'Exception'):
                    res[line.id]['purchase_status'] = 'Approved'
                if order.state == 'done' and res[line.id]['purchase_status'] not in ('Confirmed', 'Approved', 'Exception'):
                    res[line.id]['purchase_status'] = 'Done'
                if order.state in ('cancel', 'except_picking', 'except_invoice'):
                    res[line.id]['purchase_status'] = 'Exception'
                    
            # Get information about the state of all incoming shipments
            for shipment in line.incoming_ids:
                if shipment.state in ('draft', 'confirmed'):
                    res[line.id]['incoming_status'] = 'Waiting'
                if shipment.state in ('assigned') and res[line.id]['incoming_status'] not in ('Waiting'):
                    res[line.id]['incoming_status'] = 'In Progress'
                if shipment.state in ('done') and res[line.id]['incoming_status'] not in ('Waiting', 'In Progress'):
                    res[line.id]['incoming_status'] = 'Done'
                if shipment.state == 'cancel':
                    res[line.id]['incoming_status'] = 'Exception' 
            
            # Get information about the state of all outgoing deliveries
            for outgoing in line.outgoing_ids:
                if outgoing.state in ('draft', 'confirmed'):
                    res[line.id]['outgoing_status'] = 'Waiting'
                if outgoing.state in ('assigned') and res[line.id]['outgoing_status'] not in ('Waiting'):
                    res[line.id]['outgoing_status'] = 'Assigned'
                if outgoing.state in ('done') and res[line.id]['outgoing_status'] not in ('Waiting', 'Assigned'):
                    res[line.id]['outgoing_status'] = 'Done'
                if outgoing.state == 'cancel':
                    res[line.id]['outgoing_status'] = 'Exception'
            
        return res
    
    _columns = {
        'followup_id': fields.many2one('sale.order.followup', string='Sale Order Followup', required=True),
        'line_id': fields.many2one('sale.order.line', string='Order line', required=True, readonly=True),
        'line_number': fields.related('line_id', 'line_number', string='Order line', readonly=True, type='integer'),
        'product_id': fields.related('line_id', 'product_id', string='Product reference', readondy=True, 
                                     type='many2one', relation='product.product'),
        'qty_ordered': fields.related('line_id', 'product_uom_qty', string='Ordered qty', readonly=True),
        'uom_id': fields.related('line_id', 'product_uom', type='many2one', relation='product.uom', string='UoM', readonly=True),
        'sourced_ok': fields.function(_get_status, method=True, string='Sourced', type='char', 
                                   readonly=True, multi='status'),
        'tender_ids': fields.many2many('tender', 'call_tender_follow_rel',
                                       'follow_line_id', 'tender_id', string='Call for tender'),
        'tender_status': fields.function(_get_status, method=True, string='Tender', type='char',
                                         readonly=True, multi='status'),
        'quotation_ids': fields.many2many('purchase.order', 'quotation_follow_rel', 'follow_line_id',
                                          'quotation_id', string='Requests for Quotation', readonly=True),
        'quotation_status': fields.function(_get_status, method=True, string='Request for Quotation',
                                            type='char', readonly=True, multi='status'),
        'purchase_ids': fields.many2many('purchase.order', 'purchase_follow_rel', 'follow_line_id', 
                                         'purchase_id', string='Purchase Orders', readonly=True),
        'purchase_status': fields.function(_get_status, method=True, string='Purchase Order',
                                            type='char', readonly=True, multi='status'),
        'incoming_ids': fields.many2many('stock.move', 'incoming_follow_rel', 'follow_line_id', 
                                         'incoming_id', string='Incoming Shipment', readonly=True),
        'incoming_status': fields.function(_get_status, method=True, string='Incoming Shipment',
                                            type='char', readonly=True, multi='status'),
        'product_available': fields.function(_get_status, method=True, string='Product available',
                                             type='char', readonly=True, multi='status'),
        'available_qty': fields.function(_get_status, method=True, string='Product available',
                                            type='float', readonly=True, multi='status'),
        'outgoing_ids': fields.many2many('stock.move', 'outgoing_follow_rel', 'outgoing_id', 
                                         'follow_line_id', string='Outgoing Deliveries', readonly=True),
        'outgoing_status': fields.function(_get_status, method=True, string='Outgoing delivery',
                                            type='char', readonly=True, multi='status'),
    }
    
sale_order_line_followup()
