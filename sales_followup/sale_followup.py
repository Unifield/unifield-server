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
        'choose_type': lambda *a: 'progress',
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
                'target': 'dummy'}
        
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
    
    def update_followup(self, cr, uid, ids, context={}):
        '''
        Updates data in followup view
        '''
        new_context = context.copy()
        
        # Get information of the old followup before deletion
        for followup in self.browse(cr, uid, ids, context=new_context):
            new_context['active_ids'] = [followup.order_id.id]
            new_context['view_type'] = followup.choose_type
        
        # Get the id of the new followup object
        result = self.start_order_followup(cr, uid, ids, context=new_context).get('res_id')
        if not result:
            raise osv.except_osv(_('Error'), _('No followup found ! Cannot update !'))
        else:        
            # Remove the old followup object and all his lines (on delete cascade)
            self.unlink(cr, uid, ids, context=new_context)
            
        # Returns the same view as before
        if new_context.get('view_type') == 'documents':
            return self.switch_documents(cr, uid, [result], context=new_context)
        else:
            return self.switch_progress(cr, uid, [result], context=new_context)
    
    def start_order_followup(self, cr, uid, ids, context={}):
        '''
        Creates and display a followup object
        '''
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
                purchase_line_ids = self.get_purchase_line_ids(cr, uid, line.id, purchase_ids, context=context)
                incoming_ids = self.get_incoming_ids(cr, uid, line.id, purchase_ids, context=context)
                outgoing_ids = self.get_outgoing_ids(cr, uid, line.id, context=context)
                tender_ids = self.get_tender_ids(cr, uid, line.id, context=context)
#                quotation_ids = self.get_quotation_ids(cr, uid, line.id, context=context)
                
                line_obj.create(cr, uid, {'followup_id': followup_id,
                                          'line_id': line.id,
                                          'tender_ids': [(6,0,tender_ids)],
#                                          'quotation_ids': [(6,0,quotation_ids)],
                                          'purchase_ids': [(6,0,purchase_ids)],
                                          'purchase_line_ids': [(6,0,purchase_line_ids)],
                                          'incoming_ids': [(6,0,incoming_ids)],
                                          'outgoing_ids': [(6,0,outgoing_ids)],})
                    
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_line_follow_choose_view')[1]

        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order.followup',
                'res_id': followup_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',}
        
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
                if line.procurement_id.purchase_id and not line.procurement_id.purchase_id.rfq_ok:
                    purchase_ids.append(line.procurement_id.purchase_id.id)
                elif line.procurement_id.tender_id and line.procurement_id.tender_id.rfq_ids:
                    for rfq in line.procurement_id.tender_id.rfq_ids:
                        if not rfq.rfq_ok:
                            purchase_ids.append(rfq.id)
        
        return purchase_ids

    def get_purchase_line_ids(self, cr, uid, line_id, purchase_ids, context={}):
        '''
        Returns a list of purchase order lines related to the sale order line
        '''
        po_line_obj = self.pool.get('purchase.order.line')
        line_obj = self.pool.get('sale.order.line')
        po_line_ids = []

        if isinstance(purchase_ids, (int, long)):
            purchase_ids = [purchase_ids]

        if isinstance(line_id, (int, long)):
            line_id = [line_id]

        for line in line_obj.browse(cr, uid, line_id, context=context):
            po_line_ids = po_line_obj.search(cr, uid, [('order_id', 'in', purchase_ids), ('product_id', '=', line.product_id.id)], context=context)

        return po_line_ids
    
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
                if line.procurement_id.purchase_id and line.procurement_id.purchase_id.rfq_ok:
                    quotation_ids.append(line.procurement_id.purchase_id.id)
                elif line.procurement_id.tender_id and line.procurement_id.tender_id.rfq_ids:
                    for rfq in line.procurement_id.tender_id.rfq_ids:
                        if rfq.rfq_ok:
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
        move_obj = self.pool.get('stock.move')
                
        if isinstance(line_id, (int, long)):
            line_id = [line_id]
            
        outgoing_ids = []

        msf_out = self.pool.get('ir.module.module').search(cr, uid, [('name', '=', 'msf_outgoing'), ('state', '=', 'installed')], context=context)

        # If msf_outgoing is not installed
        if len(msf_out) == 0:
            for line in line_obj.browse(cr, uid, line_id, context=context):
                for move in line.move_ids:
                    if move.location_dest_id.usage == 'customer':
                        outgoing_ids.append(move.id)
        else:
            first_moves = move_obj.search(cr, uid, [('sale_line_id', 'in', line_id), ('picking_id.subtype', '=', 'picking'), ('backmove_id', '=', False)], context=context)
            picking_moves = move_obj.search(cr, uid, [('backmove_id', 'in', first_moves)], context=context)
            packing_moves = move_obj.search(cr, uid, [('backmove_id', 'in', picking_moves)], context=context)

            for first in move_obj.browse(cr, uid, first_moves, context=context):
                if first.product_qty > 0.00: 
                    outgoing_ids.append(first.id)

            if picking_moves:
                status = 'picking'
#                for pick in move_obj.browse(cr, uid, picking_moves, context=context):
#                    if pick.picking_id.subtype == 'ppl' and status != 'packing':
#                        status = 'ppl'
#                    if pick.picking_id.subtype == 'packing':
#                        status = 'packing'
                for pick in move_obj.browse(cr, uid, picking_moves, context=context):
                    if pick.product_qty > 0.00:
#                    if ((pick.product_qty > 0.00 and pick.picking_id.subtype == status) or pick.product_qty > 0.00) and pick.state != 'done':
                        outgoing_ids.append(pick.id)

            if packing_moves:
                for pack in move_obj.browse(cr, uid, packing_moves, context=context):
                    if pack.product_qty > 0.00:
                        outgoing_ids.append(pack.id)
#                    if pack.location_dest_id.usage == 'customer' or (pack.product_qty > 0.00 and pack.state != 'done'):
#                       outgoing_ids.append(pack.id)
        
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
        wh_obj = self.pool.get('stock.warehouse')

        packing_loc_ids = []
        dispatch_loc_ids = []
        distrib_loc_ids = []

        wh_ids = wh_obj.search(cr, uid, [], context=context)
        for wh in wh_obj.browse(cr, uid, wh_ids, context=context):
            if wh.lot_packing_id.id not in packing_loc_ids:
                packing_loc_ids.append(wh.lot_packing_id.id)
            if wh.lot_dispatch_id.id not in dispatch_loc_ids:
                dispatch_loc_ids.append(wh.lot_dispatch_id.id)
            if wh.lot_distribution_id.id not in distrib_loc_ids:
                distrib_loc_ids.append(wh.lot_distribution_id.id)
        
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'sourced_ok': 'Waiting',
#                            'quotation_status': 'No quotation',
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
            
            # Get information about the state of all purchase order
            if line.line_id.type == 'make_to_stock':
#                res[line.id]['quotation_status'] = 'N/A'
                res[line.id]['purchase_status'] = 'N/A'
                res[line.id]['incoming_status'] = 'N/A'
                if line.line_id.product_id:
                    context.update({'shop_id': line.line_id.order_id.shop_id.id,
                                    'uom_id': line.line_id.product_uom.id})
	            if res[line.id]['available_qty'] == 0.00:
                        res[line.id]['available_qty'] = self.pool.get('product.product').browse(cr, uid, line.line_id.product_id.id, context=context).virtual_available

            # Get information about the availability of the product
            move_ids = move_obj.search(cr, uid, [('sale_line_id', '=', line.line_id.id)])
            move_state = False
            for move in move_obj.browse(cr, uid, move_ids, context=context):
#                if move.location_dest_id.usage == 'customer':
                if move.state == 'assigned' and line.line_id.type != 'make_to_stock':
                    res[line.id]['available_qty'] += move.product_qty
                elif move.state in ('confirmed', 'waiting', 'assigned') and line.line_id.type == 'make_to_stock':
                    res[line.id]['available_qty'] += move.product_qty
                if not move_state:
                    move_state = move.state
                if move.state != move_state:
                    move_state = 'sf_partial'

            if move_state == 'sf_partial':
                res[line.id]['product_available'] = 'Partial'
            elif move_state in ('assigned', 'done'):
                res[line.id]['product_available'] = 'Done'
            elif move_state in ('draft', 'confirmed'):
                res[line.id]['product_available'] = 'Waiting'
            elif move_state == 'cancel':
                res[line.id]['product_available'] = 'Exception'

                    
            # Get information about the state of all call for tender
            tender_state = False
            if line.line_id.po_cft == 'cft' and not line.tender_ids:
                tender_state = 'no_tender'

            for tender in line.tender_ids:
                if not tender_state:
                    tender_state = tender.state
                if tender_state != tender.state:
                    tender_state = 'sf_partial'

            if tender_state == 'sf_partial':
                res[line.id]['tender_status'] = 'Partial'
            elif tender_state == 'draft':
                res[line.id]['tender_status'] = 'Waiting'
            elif tender_state == 'comparison':
                res[line.id]['tender_status'] = 'In Progress'
            elif tender_state == 'done':
                res[line.id]['tender_status'] = 'Done'
            elif tender_state == 'cancel':
                res[line.id]['tender_status'] = 'Exception'
            elif tender_state == 'no_tender':
                res[line.id]['tender_status'] = 'No tender'

            purchase_state = False
            for order in line.purchase_ids:
                if not purchase_state:
                    purchase_state = order.state
                if purchase_state != order.state:
                    purchase_state = 'sf_partial'

            if purchase_state == 'sf_partial':
                res[line.id]['purchase_status'] = 'Partial'
            elif purchase_state == 'draft':
                res[line.id]['purchase_status'] = 'Draft'
            elif purchase_state in ('confirmed', 'wait'):
                res[line.id]['purchase_status'] = 'Confirmed'
            elif purchase_state == 'approved':
                res[line.id]['purchase_status'] = 'Approved'
            elif purchase_state == 'done':
                res[line.id]['purchase_status'] = 'Done'
            elif purchase_state in ('cancel', 'except_picking', 'except_invoice'):
                res[line.id]['purchase_status'] = 'Exception'
                    
            # Get information about the state of all incoming shipments
            shipment_state = False
            for shipment in line.incoming_ids:
                if not shipment_state:
                    shipment_state = shipment.state
                if shipment_state != shipment.state:
                    shipment_state = 'sf_partial'

            if shipment_state == 'sf_partial':
                res[line.id]['incoming_status'] = 'Partial'
            elif shipment_state in ('draft', 'confirmed'):
                 res[line.id]['incoming_status'] = 'Waiting'
            elif shipment_state == 'assigned':
                res[line.id]['incoming_status'] = 'Available'
            elif shipment_state == 'done':
                res[line.id]['incoming_status'] = 'Done'
            elif shipment_state == 'cancel':
                res[line.id]['incoming_status'] = 'Exception' 

            outgoing_state = False
            product_state = False
            outgoing_partial = False
            first_move_state = False
            for outgoing in line.outgoing_ids:
                # If the line is sent in many steps
                res[line.id]['product_available'] = 'Done'
                if outgoing.product_qty < line.line_id.product_uom_qty:
                    outgoing_partial = True

                partial = True

                if outgoing.location_dest_id.usage == 'customer':
                    if outgoing.state == 'done':
                        res[line.id]['outgoing_status'] = 'Done'
                        outgoing_state = 'Done'
                        partial = False
                    else:
                        res[line.id]['outgoing_status'] = 'Shipped'
                elif outgoing.location_dest_id.id in distrib_loc_ids and \
                           res[line.id]['outgoing_status'] not in ('Done', 'Shipped'):
                    if outgoing.state == 'done':
                        res[line.id]['outgoing_status'] = 'Shipped'
                        partial = False
                    else:
                        res[line.id]['outgoing_status'] = 'Packed'
                elif outgoing.location_dest_id.id in dispatch_loc_ids and \
                           res[line.id]['outgoing_status'] not in ('Done', 'Shipped', 'Packed'):
                    if outgoing.state == 'done':
                        res[line.id]['outgoing_status'] = 'Packed'
                        partial = False
                    else:
                        res[line.id]['outgoing_status'] = 'Picked'
                else:
                    if outgoing.state == 'done':
                        res[line.id]['outgoing_status'] = 'Picked'
                        partial = False
                        first_move_state = 'Available'
                    elif outgoing.state == 'assigned':
                        res[line.id]['outgoing_status'] = 'Available'
                        res[line.id]['product_available'] = 'Available'
                        first_move_state = 'Available'
                    else:
                        res[line.id]['outgoing_status'] = 'Waiting'
                        res[line.id]['product_available'] = 'Waiting'
                        first_move_state = 'Waiting'
                    
                # Make partial state
                if partial and outgoing_partial and not outgoing_state:
                    outgoing_state = res[line.id]['outgoing_status']
                elif partial and outgoing_partial and outgoing_state and outgoing_state != res[line.id]['outgoing_status']:
                    res[line.id]['outgoing_status'] = 'Partial'
                # Make partial availability
                if outgoing_partial and not product_state:
                    product_state = res[line.id]['product_available']
                elif outgoing_partial and product_state and product_state != res[line.id]['product_available']:
                    res[line.id]['product_available'] = 'Partial'

            # In case of standard OUT (no msf_outgoing module installed)
            msf_out = self.pool.get('ir.module.module').search(cr, uid, [('name', '=', 'msf_outgoing'), ('state', '=', 'installed')], context=context)
            if not msf_out:
                for outgoing in line.outgoing_ids:
                    if outgoing.state == 'confirmed':
                        res[line.id]['outgoing_status'] = 'Waiting'
                        res[line.id]['product_available'] = 'Waiting'
                    elif outgoing.state == 'assigned':
                        res[line.id]['outgoing_status'] = 'Available'
                        res[line.id]['product_available'] = 'Available'
                    elif outgoing.state == 'done':
                        res[line.id]['outgoing_status'] = 'Done'
                        res[line.id]['product_available'] = 'Done'
                    elif outgoing.state == 'cancel':
                        res[line.id]['outgoing_status'] = 'Cancelled'
                        res[line.id]['product_available'] = 'Cancelled'

        return res
    
    _columns = {
        'followup_id': fields.many2one('sale.order.followup', string='Sale Order Followup', required=True, on_delete='cascade'),
        'line_id': fields.many2one('sale.order.line', string='Order line', required=True, readonly=True),
        'procure_method': fields.related('line_id', 'type', type='selection', selection=[('make_to_stock','From stock'), ('make_to_order','On order')], readonly=True, string='Proc. Method'),
        'po_cft': fields.related('line_id', 'po_cft', type='selection', selection=[('po','PO'), ('cft','CFT')], readonly=True, string='PO/CFT'),
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
#        'quotation_ids': fields.many2many('purchase.order', 'quotation_follow_rel', 'follow_line_id',
#                                          'quotation_id', string='Requests for Quotation', readonly=True),
#        'quotation_status': fields.function(_get_status, method=True, string='Request for Quotation',
#                                            type='char', readonly=True, multi='status'),
        'purchase_ids': fields.many2many('purchase.order', 'purchase_follow_rel', 'follow_line_id', 
                                         'purchase_id', string='Purchase Orders', readonly=True),
        'purchase_line_ids': fields.many2many('purchase.order.line', 'purchase_line_follow_rel', 'follow_line_id',
                                              'purchase_line_id', string='Purchase Orders', readonly=True),
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


class sale_order_followup_from_menu(osv.osv_memory):
    _name = 'sale.order.followup.from.menu'
    _description = 'Sale order followup menu entry'
    
    _columns = {
        'order_id': fields.many2one('sale.order', string='Sale Order', required=True),
    }
    
    def go_to_followup(self, cr, uid, ids, context={}):
        new_context = context.copy()
        new_ids = []
        for menu in self.browse(cr, uid, ids, context=context):
            new_ids.append(menu.order_id.id)
            
        new_context['active_ids'] = new_ids
        
        return self.pool.get('sale.order.followup').start_order_followup(cr, uid, ids, context=new_context)
            
sale_order_followup_from_menu()


class tender(osv.osv):
    _name = 'tender'
    _inherit = 'tender'
    
    def go_to_tender_info(self, cr, uid, ids, context={}):
        '''
        Return the form of the object
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'tender_form')[1]
        return {'type': 'ir.actions.act_window',
                'res_model': 'tender',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': ids[0],}
    
tender()


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'
    
    def go_to_po_info(self, cr, uid, ids, context={}):
        '''
        Return the form of the object
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'purchase_order_form')[1]
        po_id = self.pool.get('purchase.order.line').browse(cr, uid, ids, context=context).order_id.id
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': po_id,}
    
purchase_order()


class request_for_quotation(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'
    
    def go_to_rfq_info(self, cr, uid, ids, context={}):
        '''
        Return the form of the object
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'purchase_order_form')[1]
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': ids[0],}
    
request_for_quotation()


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'

    def _get_view_id(self, cr, uid, ids, context={}):
        '''
        Returns the good view id
        '''
        if isinstance(ids, (int,long)):
            ids = [ids]

        obj_data = self.pool.get('ir.model.data')

        pick = self.pool.get('stock.move').browse(cr, uid, ids, context=context)[0].picking_id

        view_list = {'out': ('stock', 'view_picking_out_form'),
                     'in': ('stock', 'view_picking_in_form'),
                     'internal': ('stock', 'view_picking_form'),
                     'picking': ('msf_outgoing', 'view_picking_ticket_form'),
                     'ppl': ('msf_outgoing', 'view_ppl_form'),
                     'packing': ('msf_outgoing', 'view_packing_form')
                     }
        if pick.type == 'out':
            module, view = view_list.get(pick.subtype,('msf_outgoing', 'view_picking_ticket_form'))[1], pick.id
            try:
                return obj_data.get_object_reference(cr, uid, module, view)
            except ValueError, e:
                pass
        
        module, view = view_list.get(pick.type,('stock', 'view_picking_form'))

        return self.pool.get('ir.model.data').get_object_reference(cr, uid, module, view)[1], pick.id
    
    def go_to_incoming_info(self, cr, uid, ids, context={}):
        '''
        Return the form of the object
        '''
        view_id = self._get_view_id(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id[0]],
                'res_id': view_id[1],}
        
    def go_to_outgoing_info(self, cr, uid, ids, context={}):
        '''
        Return the form of the object
        '''
        view_id = self._get_view_id(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id[0]],
                'res_id': view_id[1],}
    
stock_move()


class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    STATE_SELECTION = [
                       ('draft', 'Draft'),
                       ('wait', 'Waiting'),
                       ('confirmed', 'Waiting Approval'),
                       ('approved', 'Approved'),
                       ('except_picking', 'Shipping Exception'),
                       ('except_invoice', 'Invoice Exception'),
                       ('done', 'Done'),
                       ('cancel', 'Cancelled'),
                       ('rfq_sent', 'RfQ Sent'),
                       ('rfq_updated', 'RfQ Updated'),
                       ('rfq_done', 'RfQ Done'),
    ]

    ORDER_TYPE = [('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                        ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                        ('direct', 'Direct Purchase Order')]

    _columns = {
        'order_type': fields.related('order_id', 'order_type', type='selection', selection=ORDER_TYPE, readonly=True),
        'po_state': fields.related('order_id', 'state', type='selection', selection=STATE_SELECTION, readonly=True),
    }

    def go_to_po_info(self, cr, uid, ids, context={}):
        '''
        Return the form of the object
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'purchase_order_form')[1]
        if isinstance(ids, (int,long)):
            ids = [ids]
        po_id = self.pool.get('purchase.order.line').browse(cr, uid, ids, context=context)[0].order_id.id
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': po_id,}

purchase_order_line()
