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
import datetime

class sale_order_followup_test(osv.osv_memory):
    _name = 'sale.order.followup.test'

    _columns = {'name': fields.char(size=64, string='Name')}

    def create_test(self, cr, uid, ids, context=None):
        self.pool.get('product.category').create(cr, uid, {'name': 'test category'}, context=context)
        return True

sale_order_followup_test()

class sale_order_followup(osv.osv_memory):
    _name = 'sale.order.followup'
    _description = 'Sales Order Followup'

    def get_selection(self, cr, uid, o, field, context=None):
        """
        """
        return self.pool.get('ir.model.fields').get_browse_selection(cr, uid, o, field, context)


    def _get_order_state(self, cr, uid, ids, field_name, args, context=None):
        if not context:
            context = {}

        res = {}

        for follow in self.browse(cr, uid, ids, context=context):
            res[follow.id] = None

            if follow.order_id:
                res[follow.id] = self.get_selection(cr, uid, follow.order_id, 'state_hidden_sale_order', context)

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

    def go_to_view(self, cr, uid, ids, context=None):
        '''
        Launches the correct view according to the user's choice
        '''
        for followup in self.browse(cr, uid, ids, context=context):
            split = False
            for line in followup.order_id.order_line:
                if self.pool.get('sale.order.line').search(cr, uid, [('original_line_id', '=', line.id)], context=context):
                    split = True
#            if followup.choose_type == 'documents':
#                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_followup_document_view')[1]
#            else:
            if split:
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_followup_split_progress_view')[1]
            else:
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_followup_progress_view')[1]

        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order.followup',
                'res_id': followup.id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'dummy'}

#    def switch_documents(self, cr, uid, ids, context=None):
#        '''
#        Switch to documents view
#        '''
#        self.write(cr, uid, ids, {'choose_type': 'documents'})
#
#        return self.go_to_view(cr, uid, ids, context=context)

    def switch_progress(self, cr, uid, ids, context=None):
        '''
        Switch to progress view
        '''
        self.write(cr, uid, ids, {'choose_type': 'progress'})

        return self.go_to_view(cr, uid, ids, context=context)

    def update_followup(self, cr, uid, ids, context=None):
        '''
        Updates data in followup view
        '''
        if context is None:
            context = {}
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
        #if new_context.get('view_type') == 'documents':
        #    return self.switch_documents(cr, uid, [result], context=new_context)
        #else:
        return self.switch_progress(cr, uid, [result], context=new_context)

    def start_order_followup(self, cr, uid, ids, context=None):
        '''
        Creates and display a followup object
        '''
        order_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        line_obj = self.pool.get('sale.order.line.followup')

        if context is None:
            context = {}

        # openERP BUG ?
        ids = context.get('active_ids',[])

        if not ids:
            raise osv.except_osv(_('Error'), _('No order found !'))
        if len(ids) != 1:
            raise osv.except_osv(_('Error'), _('You should select one order to follow !'))

        followup_id = False
        split_lines = False
        for o in order_obj.browse(cr, uid, ids, context=context):
            followup_id = self.create(cr, uid, {'order_id': o.id}, context=context)

            for line in o.order_line:
                split_line_ids = sol_obj.search(cr, uid, [('original_line_id', '=', line.id)], context=context)
                first_line = True
                if split_line_ids:
                    split_lines = True
                    lines = sol_obj.browse(cr, uid, split_line_ids, context=context)
                else:
                    lines = [line]

                for l in lines:
                    purchase_ids = self.get_purchase_ids(cr, uid, l.id, context=context)
                    purchase_line_ids = self.get_purchase_line_ids(cr, uid, l.id, purchase_ids, context=context)
                    incoming_ids = self.get_incoming_ids(cr, uid, l.id, purchase_ids, context=context)
                    outgoing_ids = self.get_outgoing_ids(cr, uid, l.id, context=context)
                    displayed_out_ids = self.get_outgoing_ids(cr, uid, l.id, non_zero=True, context=context)
                    tender_ids = self.get_tender_ids(cr, uid, l.id, context=context)
#                    quotation_ids = self.get_quotation_ids(cr, uid, line.id, context=context)

                    line_obj.create(cr, uid, {'followup_id': followup_id,
                                              'line_id': line.id,
                                              'original_order_id': split_lines and l.order_id and l.order_id.id or False,
                                              'first_line': first_line,
                                              'tender_ids': [(6,0,tender_ids)],
                                              #                                             'quotation_ids': [(6,0,quotation_ids)],
                                              'purchase_ids': [(6,0,purchase_ids)],
                                              'purchase_line_ids': [(6,0,purchase_line_ids)],
                                              'incoming_ids': [(6,0,incoming_ids)],
                                              'outgoing_ids': [(6,0,outgoing_ids)],
                                              'displayed_out_ids': [(6,0,displayed_out_ids)]}, context=context)
                    first_line = False

        if split_lines:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_followup_split_progress_view')[1]
        else:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sales_followup', 'sale_order_followup_progress_view')[1]

        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order.followup',
                'res_id': followup_id,
                'view_id': [view_id],
                'nodestroy': True,
                'view_type': 'form',
                'view_mode': 'form',}

    def get_purchase_ids(self, cr, uid, line_id, context=None):
        '''
        Returns a list of purchase orders related to the sale order line
        '''
        if context is None:
            context = {}
        if isinstance(line_id, int):
            line_id = [line_id]

        po_ids = set()
        for sol in self.pool.get('sale.order.line').browse(cr, uid, line_id, context=context):
            linked_pol = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', '=', sol.id)])
            if sol.type == 'make_to_order' and linked_pol:
                linked_pol = self.pool.get('purchase.order.line').browse(cr, uid, linked_pol, context=context)[0]
                if not linked_pol.order_id.rfq_ok:
                    po_ids.add(linked_pol.order_id.id)

        return list(po_ids)

    def get_purchase_line_ids(self, cr, uid, line_id, purchase_ids, context=None):
        '''
        Returns a list of purchase order lines related to the sale order line
        '''
        po_line_obj = self.pool.get('purchase.order.line')
        line_obj = self.pool.get('sale.order.line')
        po_line_ids = []

        if isinstance(purchase_ids, int):
            purchase_ids = [purchase_ids]

        if isinstance(line_id, int):
            line_id = [line_id]

        for line in line_obj.browse(cr, uid, line_id, context=context):
            po_line_ids = po_line_obj.search(cr, uid, [('order_id', 'in', purchase_ids), ('product_id', '=', line.product_id.id)], context=context)

        return po_line_ids

    def get_quotation_ids(self, cr, uid, line_id, context=None):
        '''
        Returns a list of request for quotation related to the sale order line
        '''
        if context is None:
            context = {}
        if isinstance(line_id, int):
            line_id = [line_id]

        rfq_ids = set()
        for sol in self.pool.get('sale.order.line').browse(cr, uid, line_id, context=context):
            linked_pol = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', '=', sol.id)])
            if sol.type == 'make_to_order' and linked_pol:
                linked_pol = self.pool.get('purchase.order.line').browse(cr, uid, linked_pol, context=context)[0]
                if linked_pol.order_id.rfq_ok:
                    rfq_ids.add(linked_pol.order_id.id)

        return rfq_ids

    def get_incoming_ids(self, cr, uid, line_id, purchase_ids, context=None):
        '''
        Returns a list of incoming shipments related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')
        purchase_obj = self.pool.get('purchase.order')

        if isinstance(line_id, int):
            line_id = [line_id]

        if isinstance(purchase_ids, int):
            purchase_ids= [purchase_ids]

        incoming_ids = []

        for line in line_obj.browse(cr, uid, line_id, context=context):
            for po in purchase_obj.browse(cr, uid, purchase_ids, context=context):
                for po_line in po.order_line:
                    if po_line.product_id.id == line.product_id.id:
                        for move in po_line.move_ids:
                            incoming_ids.append(move.id)

        return incoming_ids

    def get_outgoing_ids(self, cr, uid, line_id, non_zero=False, context=None):
        '''
        Returns a list of outgoing deliveries related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')

        if isinstance(line_id, int):
            line_id = [line_id]

        outgoing_ids = []

        # Get all stock.picking associated to the sale order line
        for line in line_obj.browse(cr, uid, line_id, context=context):
            for move in line.move_ids:
                if move.id not in outgoing_ids and (not non_zero or (non_zero and move.product_qty != 0.00)):
                    outgoing_ids.append(move.id)
#                if move.picking_id and move.picking_id.id not in outgoing_ids:
#                    outgoing_ids.append(move.picking_id.id)

        return outgoing_ids

    def get_tender_ids(self, cr, uid, line_id, context=None):
        '''
        Returns a list of call for tender related to the sale order line
        '''
        line_obj = self.pool.get('sale.order.line')

        if isinstance(line_id, int):
            line_id = [line_id]

        tender_ids = []

        for line in line_obj.browse(cr, uid, line_id, context=context):
            for tender in line.tender_line_ids:
                tender_ids.append(tender.id)

        return tender_ids

    def export_get_file_name(self, cr, uid, ids, prefix='FO_Follow_Up', context=None):
        if isinstance(ids, int):
            ids = [ids]
        if len(ids) != 1:
            return False
        foup = self.browse(cr, uid, ids[0], context=context)
        if not foup or not foup.order_id or not foup.order_id.name:
            return False
        dt_now = datetime.datetime.now()
        po_name = "%s_%s_%d_%02d_%02d" % (prefix,
                                          foup.order_id.name.replace('/', '_'),
                                          dt_now.year, dt_now.month, dt_now.day)
        return po_name

    def export_xls(self, cr, uid, ids, context=None):
        """
        Print the report (Excel)
        """
        if isinstance(ids, int):
            ids = [ids]
        datas = {'ids': ids}
        file_name = self.export_get_file_name(cr, uid, ids, context=context)
        if file_name:
            datas['target_filename'] = file_name
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sales.follow.up.report_xls',
            'datas': datas,
            'context': context,
            'nodestroy': True,
        }

    def export_pdf(self, cr, uid, ids, context=None):
        """
        Print the report (PDF)
        """
        if isinstance(ids, int):
            ids = [ids]
        datas = {'ids': ids}
        file_name = self.export_get_file_name(cr, uid, ids, context=context)
        if file_name:
            datas['target_filename'] = file_name
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sales.follow.up.report_pdf',
            'datas': datas,
            'context': context,
            'nodestroy': True,
        }

sale_order_followup()


class sale_order_line_followup(osv.osv_memory):
    _name = 'sale.order.line.followup'
    _description = 'Sales Order Lines Followup'

    def _get_status(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Get all status about the line
        '''
        res = {}
        if context is None:
            context = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'sourced_ok': _('No'),
                            #                            'quotation_status': 'No quotation',
                            'tender_status': _('N/A'),
                            'purchase_status': _('N/A'),
                            'incoming_status': _('N/A'),
                            'outgoing_status': _('No deliveries'),
                            'product_available': _('Waiting'),
                            'outgoing_nb': 0,
                            'available_qty': 0.00}

            # Set the available qty in stock
            # You may not have product with an Internal Request
            if line.line_id.product_id:
                res[line.id]['available_qty'] = self.pool.get('product.product').browse(cr, uid, line.line_id.product_id.id, context=context).qty_available

            # Define if the line is sourced or not according to the state on the SO line
            if line.line_id.state == 'draft':
                res[line.id]['sourced_ok'] = _('No')
            if line.line_id.state in ('confirmed', 'done'):
                res[line.id]['sourced_ok'] = _('Closed')
            if line.line_id.state == 'cancel':
                res[line.id]['sourced_ok'] = _('Cancelled')
            if line.line_id.state == 'exception':
                res[line.id]['sourced_ok'] = _('Exception')

            ####################################################
            # Get information about the state of call for tender
            ####################################################
            tender_status = {'n_a': _('N/A'),
                             'no_tender': _('No tender'),
                             'partial': _('Partial'),
                             'draft': _('Waiting'),
                             'comparison': _('In Progress'),
                             'done': _('Closed'),
                             'cancel': _('Cancelled')}

            if line.line_id.type == 'make_to_stock' or line.line_id.po_cft in ('po', 'dpo'):
                res[line.id]['tender_status'] = tender_status.get('n_a', _('Error on state !'))
            elif line.line_id.po_cft == 'cft' and not line.tender_ids:
                res[line.id]['tender_status'] = tender_status.get('no_tender', _('Error on state !'))
            else:
                # Check if all generated tenders are in the same state
                tender_state = False
                for tender in line.tender_ids:
                    if not tender_state:
                        tender_state = tender.state
                    if tender_state != tender.state:
                        tender_state = 'partial'

                res[line.id]['tender_status'] = tender_status.get(tender_state, _('Error on state !'))

            # Add number of documents in brackets
            res[line.id]['tender_status'] = '%s (%s)' % (res[line.id]['tender_status'], len(line.tender_ids))

            ####################################################
            # Get information about the state of purchase orders
            ####################################################
            purchase_status = {'n_a': _('N/A'),
                               'no_order': _('No order'),
                               'partial': _('Partial'),
                               'draft': _('Draft'),
                               'confirmed': _('Validated'),
                               'wait': _('Validated'),
                               'confirmed_wait': _('Confirmed (waiting)'),
                               'approved': _('Confirmed'),
                               'done': _('Closed'),
                               'sourced': _('Sourced'),
                               'cancel': _('Cancelled'),
                               'except_picking': _('Exception'),
                               'except_invoice': _('Exception'),}

            if line.line_id.type == 'make_to_stock':
                res[line.id]['purchase_status'] = purchase_status.get('n_a', _('Error on state !'))
            elif not line.purchase_ids:
                res[line.id]['purchase_status'] = purchase_status.get('no_order', _('Error on state !'))
            else:
                # Check if all generated PO are in the same state
                purchase_state = False
                for order in line.purchase_ids:
                    if not purchase_state:
                        purchase_state = order.state
                    if purchase_state != order.state:
                        purchase_state = 'partial'

                res[line.id]['purchase_status'] = purchase_status.get(purchase_state, _('Error on state !'))

            # Add number of documents in brackets
            res[line.id]['purchase_status'] = '%s (%s)' % (res[line.id]['purchase_status'], len(line.purchase_ids))

            ###########################################################
            # Get information about the state of all incoming shipments
            ###########################################################
            incoming_status = {'n_a': _('N/A'),
                               'no_incoming': _('No shipment'),
                               'partial': _('Partial'),
                               'draft': _('Waiting'),
                               'confirmed': _('Waiting'),
                               'assigned': _('Available'),
                               'done': _('Closed'),
                               'cancel': _('Cancelled')}

            if line.line_id.type == 'make_to_stock':
                res[line.id]['incoming_status'] = incoming_status.get('n_a', _('Error on state !'))
            elif not line.incoming_ids:
                res[line.id]['incoming_status'] = incoming_status.get('no_incoming', _('Error on state !'))
            else:
                shipment_state = False
                for shipment in line.incoming_ids:
                    if not shipment_state:
                        shipment_state = shipment.state
                    if shipment_state != shipment.state:
                        shipment_state = 'partial'

                res[line.id]['incoming_status'] = incoming_status.get(shipment_state, _('Error on state !'))

            # Add number of documents in brackets
            res[line.id]['incoming_status'] = '%s (%s)' % (res[line.id]['incoming_status'], len(line.incoming_ids))

            #######################################################################
            # Get information about the step and the state of all outgoing delivery
            #######################################################################
            out_status = {'no_out': _('No deliveries'),
                          'partial': _('Partial'),
                          'draft': _('Waiting'),
                          'confirmed': _('Waiting'),
                          'assigned': _('Available'),
                          'done': _('Closed'),
                          'picked': _('Picked'),
                          'packed': _('Packed'),
                          'shipped': _('Shipped'),
                          'cancel': _('Cancelled'),}

            if not line.outgoing_ids:
                res[line.id]['outgoing_status'] = out_status.get('no_out', _('Error on state !'))
                res[line.id]['outgoing_nb'] = '0'
            else:
                # Get the first stock.picking
                first_out = False
                moves_first_out = []
                moves_first_out_ids = []
                for out in line.outgoing_ids:
                    if out.picking_id and not out.picking_id.previous_step_id:
                        first_out = out.picking_id
                        moves_first_out.append(out)
                        moves_first_out_ids.append(out.id)

                # Check the flow type of the first picking (full or quick)
                if first_out.subtype == 'standard':
                    res[line.id]['outgoing_nb'] = len(moves_first_out)
                    out_state = False
                    for out in moves_first_out:
                        if not out_state:
                            out_state = out.state
                        if out.state != out_state:
                            out_state = 'partial'

                    res[line.id]['outgoing_status'] = out_status.get(out_state, _('Error on state !'))
                    res[line.id]['product_available'] = out_status.get(out_state, _('Error on state !'))
                else:
                    # Full mode
                    # Begin from the first out moves
                    ppl_ids = []
                    out_step = {'general': {'moves': [], 'state': False},
                                'picking': {'moves': [], 'state': False},
                                'packing': {'moves': [], 'state': False},
                                'dispatch': {'moves': [], 'state': False},
                                'distrib': {'moves': [], 'state': False},
                                'customer': {'moves': [], 'state': False},}

                    # Sort outgoing moves by type (picking, packing, dispatch, distrib, sending)
                    for out in line.outgoing_ids:
                        if not out.backmove_id:
                            out_step['general']['moves'].append(out)
                        elif out.backmove_id.id in moves_first_out_ids and out.picking_id and out.picking_id.subtype == 'picking':
                            out_step['picking']['moves'].append(out)
                        elif out.backmove_id.id in moves_first_out_ids and out.picking_id and out.picking_id.subtype == 'ppl':
                            out_step['packing']['moves'].append(out)
                            ppl_ids.append(out.picking_id.id)
                        elif out.backmove_id.id in moves_first_out_ids and out.picking_id and out.picking_id.subtype == 'packing':
                            if out.location_dest_id.usage == 'customer':
                                out_step['customer']['moves'].append(out)
                            elif out.location_dest_id.id == out.picking_id.warehouse_id.lot_distribution_id.id:
                                out_step['distrib']['moves'].append(out)
                            elif out.location_dest_id.id == out.picking_id.warehouse_id.lot_dispatch_id.id:
                                out_step['dispatch']['moves'].append(out)
                            elif out.location_id.id == out.picking_id.warehouse_id.lot_dispatch_id.id:
                                out_step['dispatch']['moves'].append(out)
                            elif out.location_id.id == out.picking_id.warehouse_id.lot_distribution_id.id:
                                out_step['distrib']['moves'].append(out)

                    nb_out = len(out_step['picking']['moves'])

                    nb_return_pack = 0
                    nb_return_pack2 = 0
                    for pack in out_step['packing']['moves']:
                        if pack.state == 'done' and pack.product_qty == 0.00:
                            nb_return_pack += 1

                    nb_return_dist = 0
                    for cust in out_step['customer']['moves']:
                        if cust.state == 'done' and cust.product_qty == 0.00:
                            nb_return_dist += 1

                    # Set the state for the step 'customer'
                    ret_iter = 0
                    for cust in out_step['customer']['moves']:
                        if cust.state == 'done' and ret_iter != nb_return_dist:
                            ret_iter += 1
                            continue
                        if not out_step['customer']['state']:
                            out_step['customer']['state'] = cust.state
                        if out_step['customer']['state'] != cust.state:
                            out_step['customer']['state'] = 'partial'

                    # Set the state for the step 'distrib'
                    ret_iter = 0
                    for dist in out_step['distrib']['moves']:
                        if dist.state == 'cancel' or dist.product_qty == 0.00:
                            continue
                        if dist.state == 'done' and ret_iter != nb_return_dist:
                            ret_iter += 1
                            continue
                        if not out_step['distrib']['state']:
                            out_step['distrib']['state'] = dist.state
                        if out_step['distrib']['state'] != dist.state:
                            out_step['distrib']['state'] = 'partial'

                    # Set the state for the step 'dispatch'
                    for disp in out_step['dispatch']['moves']:
                        if disp.location_id.id == disp.picking_id.warehouse_id.lot_dispatch_id.id:
                            nb_return_pack2 += 1
                            nb_out -= 1
                        if not out_step['dispatch']['state']:
                            out_step['dispatch']['state'] = disp.state
                        if out_step['dispatch']['state'] != disp.state:
                            out_step['dispatch']['state'] = 'partial'

                    # Set the state for the step 'packing'
                    ret_iter = 0
                    for pack in out_step['packing']['moves']:
                        if pack.product_qty == 0.00 or pack.location_dest_id.id != pack.picking_id.warehouse_id.lot_dispatch_id.id:
                            continue
                        if pack.state == 'done' and ret_iter != (nb_return_pack + nb_return_pack2):
                            ret_iter += 1
                            continue
                        if not out_step['packing']['state']:
                            out_step['packing']['state'] = pack.state
                        if out_step['packing']['state'] != pack.state:
                            out_step['packing']['state'] = 'partial'

                    # Set the state for the step 'picking'
                    ret_iter = 0
                    ret_iter2 = 0
                    for pick in out_step['picking']['moves']:
                        if pick.state == 'cancel':
                            nb_out -= 1
                            continue
                        if pick.state == 'done' and ret_iter != nb_return_pack:
                            nb_out -= 1
                            ret_iter += 1
                            continue
                        elif pick.state == 'done' and ret_iter2 != nb_return_pack2:
                            ret_iter2 += 1
#                            nb_out -= 1
                            continue
                        if not out_step['picking']['state']:
                            out_step['picking']['state'] = pick.state
                        if out_step['picking']['state'] != pick.state:
                            out_step['picking']['state'] = 'partial'

                    # Increase the nb of out if there are products in general picking ticket
                    total_line = 0.00
                    for general in out_step['general']['moves']:
                        if general.product_qty != 0.00 and general.state != 'cancel':
                            total_line += general.product_qty
                            nb_out += 1
                            out_step['general']['state'] = general.state

                    all_done = True
                    for step in out_step:
                        if out_step[step]['state'] and out_step[step]['state'] != 'done':
                            all_done = False

                    # If all products should be processed from the main picking ticket or if the main picking ticket is done
                    if total_line == line.line_id.product_uom_qty:
                        res[line.id]['product_available'] = out_status.get(out_step['general']['state'], _('Error on state !'))
                        res[line.id]['outgoing_status'] = out_status.get(out_step['general']['state'], _('Error on state !'))
                    elif total_line < line.line_id.product_uom_qty and out_step['general']['state']:
                        res[line.id]['product_available'] = out_status.get('partial', _('Error on state !'))
                        res[line.id]['outgoing_status'] = out_status.get('partial', _('Error on state !'))
                    elif out_step['customer']['state'] == 'done' and all_done:
                        res[line.id]['product_available'] = out_status.get('done', _('Error on state !'))
                        res[line.id]['outgoing_status'] = out_status.get('done', _('Error on state !'))
                    else:
                        # If not all products are sent to the supplier
                        if out_step['customer']['state'] and out_step['customer']['state'] == 'partial':
                            res[line.id]['outgoing_status'] = out_status.get('partial', _('Error on state !'))
                            res[line.id]['product_available'] = out_status.get('done', _('Error on state !'))
                        # If all products are waiting to send to customer
                        elif out_step['customer']['state'] and out_step['customer']['state'] == 'assigned':
                            res[line.id]['outgoing_status'] = out_status.get('shipped', _('Error on state !'))
                            res[line.id]['product_available'] = out_status.get('done', _('Error on state !'))

                        # If all products are not in distribution
                        if out_step['distrib']['state'] and out_step['distrib']['state'] == 'partial':
                            res[line.id]['outgoing_status'] = out_status.get('partial', _('Error on state !'))
                        elif out_step['distrib']['state'] and out_step['distrib']['state'] == 'assigned':
                            res[line.id]['outgoing_status'] = out_status.get('packed', _('Error on state !'))
                            res[line.id]['product_available'] = out_status.get('done', _('Error on state !'))

                        # If all products are not in dispatch zone
                        if out_step['dispatch']['state'] == 'partial':
                            res[line.id]['outgoing_status'] = out_status.get('partial', _('Error on state !'))

                        # If all products are not picked
                        if out_step['picking']['state'] == 'partial' or out_step['packing']['state'] == 'partial':
                            res[line.id]['outgoing_status'] = out_status.get('partial', 'Error on state !')
                            res[line.id]['product_available'] = out_status.get(out_step['picking']['state'], _('Error on state !'))
                        elif out_step['picking']['state'] == 'assigned':
                            res[line.id]['outgoing_status'] = out_status.get('assigned', _('Error on state !'))
                            res[line.id]['product_available'] = out_status.get('assigned', _('Error on state !'))
                        elif out_step['picking']['state'] == 'done' and out_step['packing']['state'] == 'assigned':
                            res[line.id]['outgoing_status'] = out_status.get('picked', _('Error on state !'))
                            res[line.id]['product_available'] = out_status.get('done', _('Error on state !'))

                        if out_step['picking']['state'] == 'done':
                            res[line.id]['product_available'] = out_status.get('done', _('Error on state !'))

                    # Set the number of the outgoing deliveries
                    res[line.id]['outgoing_nb'] = '%s' %nb_out

            # Add the namber of documents in brackets
            res[line.id]['outgoing_status'] = '%s (%s)' % (res[line.id]['outgoing_status'], res[line.id]['outgoing_nb'])
            res[line.id]['product_available'] = '%s (%s)' % (res[line.id]['product_available'], res[line.id]['available_qty'])

        return res

    _columns = {
        'followup_id': fields.many2one('sale.order.followup', string='Sale Order Followup', required=True, on_delete='cascade'),
        'line_id': fields.many2one('sale.order.line', string='Order line', required=True, readonly=True),
        'original_order_id': fields.many2one('sale.order', string='Orig. line', readonly=True),
        'first_line': fields.boolean(string='First line'),
        'procure_method': fields.related('line_id', 'type', type='selection', selection=[('make_to_stock','From stock'), ('make_to_order','On order')], readonly=True, string='Proc. Method'),
        'po_cft': fields.related('line_id', 'po_cft', type='selection', selection=[('po','PO'), ('dpo', 'DPO'), ('cft','CFT'), ('pli', 'PLI')], readonly=True, string='PO/CFT'),
        'line_number': fields.related('line_id', 'line_number', string='Order line', readonly=True, type='integer'),
        'product_id': fields.related('line_id', 'product_id', string='Product Code', readonly=True,
                                     type='many2one', relation='product.product'),
        'qty_ordered': fields.related('line_id', 'product_uom_qty', string='Ordered qty', readonly=True, related_uom='uom_id'),
        'uom_id': fields.related('line_id', 'product_uom', type='many2one', relation='product.uom', string='UoM', readonly=True),
        'sourced_ok': fields.function(_get_status, method=True, string='Sourced', type='char',
                                      readonly=True, multi='status'),
        'tender_ids': fields.many2many('tender.line', 'call_tender_follow_rel',
                                       'follow_line_id', 'tender_id', string='Tender'),
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
        'displayed_out_ids': fields.many2many('stock.move', 'displayed_out_follow_rel', 'diplayed_out_id',
                                              'follow_line_id', string='Outgoing Deliveries', readonly=True),
        'outgoing_status': fields.function(_get_status, method=True, string='Outgoing delivery',
                                           type='char', readonly=True, multi='status'),
        'outgoing_nb': fields.function(_get_status, method=True, string='Outgoing delivery',
                                       type='char', readonly=True, multi='status'),
    }

sale_order_line_followup()


class sale_order_followup_from_menu(osv.osv_memory):
    _name = 'sale.order.followup.from.menu'
    _description = 'Sale order followup menu entry'

    _columns = {
        'order_id': fields.many2one('sale.order', string='Internal reference', required=True, domain=[('procurement_request', '=', False)]),
        'cust_order_id': fields.many2one('sale.order', string='Customer reference', required=True, domain=[('procurement_request', '=', False)]),
    }

    def go_to_followup(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        new_context = context.copy()
        new_ids = []
        for menu in self.browse(cr, uid, ids, context=context):
            new_ids.append(menu.order_id and menu.order_id.id or menu.cust_order_id.id)

        new_context['active_ids'] = new_ids

        return self.pool.get('sale.order.followup').start_order_followup(cr, uid, ids, context=new_context)

    def change_order_id(self, cr, uid, ids, order_id, cust_order_id, type='order_id'):
        res = {}

        if type == 'cust_order_id' and cust_order_id:
            res.update({'order_id': False})
        elif order_id:
            res.update({'cust_order_id': False})

        return {'value': res}


sale_order_followup_from_menu()


class tender_line(osv.osv):
    _name = 'tender.line'
    _inherit = 'tender.line'

    def go_to_tender_info(self, cr, uid, ids, context=None):
        '''
        Return the form of the object
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'tender_form')[1]
        tender_id = self.pool.get('tender.line').browse(cr, uid, ids[0], context=context).tender_id.id
        return {'type': 'ir.actions.act_window',
                'res_model': 'tender',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': tender_id,}

tender_line()


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def go_to_po_info(self, cr, uid, ids, context=None):
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

    def go_to_rfq_info(self, cr, uid, ids, context=None):
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

    def _get_view_id(self, cr, uid, ids, context=None):
        '''
        Returns the good view id
        '''
        if isinstance(ids, int):
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
            module, view = view_list.get(pick.subtype,('msf_outgoing', 'view_picking_ticket_form'))
            try:
                return obj_data.get_object_reference(cr, uid, module, view)[1], pick.id
            except ValueError:
                pass

        module, view = view_list.get(pick.type,('stock', 'view_picking_form'))

        return self.pool.get('ir.model.data').get_object_reference(cr, uid, module, view)[1], pick.id

    def go_to_incoming_info(self, cr, uid, ids, context=None):
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

    def go_to_outgoing_info(self, cr, uid, ids, context=None):
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
        ('wait', 'Wait'),
        ('confirmed', 'Validated'),
        ('approved', 'Confirmed'),
        ('confirmed_wait', 'Confirmed (waiting)'),
        ('except_picking', 'Receipt Exception'),
        ('except_invoice', 'Invoice Exception'),
        ('done', 'Closed'),
        ('cancel', 'Cancelled'),
        ('rfq_sent', 'Sent'),
        ('rfq_updated', 'Updated'),
    ]

    ORDER_TYPE = [('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                  ('donation_st', 'Standard donation'), ('loan', 'Loan'),
                  ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                  ('direct', 'Direct Purchase Order')]

    _columns = {
        'order_type': fields.related('order_id', 'order_type', type='selection', selection=ORDER_TYPE, readonly=True),
        'po_state': fields.related('order_id', 'state', type='selection', selection=STATE_SELECTION, readonly=True),
    }

    def go_to_po_info(self, cr, uid, ids, context=None):
        '''
        Return the form of the object
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'purchase_order_form')[1]
        if isinstance(ids, int):
            ids = [ids]
        po_id = self.pool.get('purchase.order.line').browse(cr, uid, ids, context=context)[0].order_id.id
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': po_id,}

purchase_order_line()


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for so_id in ids:
            res[so_id] = True

        return res

    def _src_to_partner(self, cr, uid, obj, name, args, context=None):
        res = []

        for arg in args:
            if arg[0] == 'to_partner_id' and arg[2] is not False:
                res.append(('partner_id', arg[1], arg[2]))

        return res

    _columns = {
        'to_partner_id': fields.function(
            _get_dummy,
            fnct_search=_src_to_partner,
            method=True,
            type='boolean',
            string='To partner',
            readonly=True,
            store=False,
        ),
    }

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=80):
        '''
        Search all SO by internal or customer reference
        '''
        if context is None:
            context = {}
        if context.get('from_followup'):
            ids = []
            if name and len(name) > 1:
                args2 = [('client_order_ref', operator, name)]
                if args:
                    args2 += args
                ids.extend(self.search(cr, uid, args2, context=context))
            res = self.name_get(cr, uid, ids, context=context)
        else:
            res = super(sale_order, self).name_search(cr, uid, name, args, operator, context, limit)
        return res

    def name_get(self, cr, uid, ids, context=None):
        '''
        If the method is called from followup wizard, set the customer ref in brackets
        '''
        if context is None:
            context = {}
        if context.get('from_followup'):
            res = []
            for r in self.browse(cr, uid, ids, context=context):
                if r.client_order_ref:
                    res.append((r.id, '%s' % r.client_order_ref))
                else:
                    res.append((r.id, '%s' % r.name))
            return res
        else:
            return super(sale_order, self).name_get(cr, uid, ids, context=context)

sale_order()
