# -*- coding: utf-8 -*-

from osv import osv
import netsvc
from tools.translate import _
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta



class purchase_order_line(osv.osv):
    _name = "purchase.order.line"
    _inherit = "purchase.order.line"

    def get_split_info(self, cr, uid, pol, context=None):
        sol_values = {}

        if pol.is_line_split:
            split_po_ids = self.search(cr, uid, [('is_line_split', '=', False), ('line_number', '=', pol.line_number), ('order_id', '=', pol.order_id.id)], context=context)
            if split_po_ids:
                split_po = self.browse(cr, uid, split_po_ids[0], context=context)
                if split_po.linked_sol_id:
                    sol_values['line_number'] = split_po.linked_sol_id.line_number
        return sol_values

    def update_fo_lines(self, cr, uid, ids, context=None):
        '''
        update corresponding FO lines in the same instance
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        for pol in self.browse(cr, uid, ids, context=context):
            # linked FO line already exists ?
            # => if yes update it, else create new
            create_line = False
            if not pol.linked_sol_id:
                # try to get the linked sale.order:
                so_id = pol.link_so_id.id
                if not so_id:
                    so_id = self.pool.get('sale.order').search(cr, uid, [
                        ('name', '=', pol.origin),
                        ('procurement_request', 'in', ['t', 'f']),
                    ], context=context)
                    so_id = so_id and so_id[0] or False
                if not so_id:
                    continue # no sale order linked to our PO line
                sale_order = self.pool.get('sale.order').browse(cr, uid, so_id, context=context)
                create_line = True
            elif pol.linked_sol_id:
                sale_order = pol.linked_sol_id.order_id
            else:
                # case of PO line from scratch, nothing to update
                continue 

            # convert from currency of pol to currency of sol
            price_unit_converted = self.pool.get('res.currency').compute(cr, uid, pol.currency_id.id, sale_order.currency_id.id, pol.price_unit or 0.0,
                                                                         round=False, context={'date': pol.order_id.date_order})

            if sale_order.order_type == 'regular' and price_unit_converted < 0.00001:
                price_unit_converted = 0.00001

            # date values
            ship_lt = self.pool.get('fields.tools').get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
            prep_lt = self.pool.get('fields.tools').get_field_from_company(cr, uid, object=self._name, field='preparation_lead_time', context=context)
            db_date_format = self.pool.get('date.tools').get_db_date_format(cr, uid, context=context)

            # compute confirmed date for line:
            line_confirmed = False
            if pol.confirmed_delivery_date:
                line_confirmed = self.pool.get('purchase.order').compute_confirmed_delivery_date(cr, uid, pol.order_id, pol.confirmed_delivery_date,
                                                                                                 prep_lt, ship_lt, sale_order.est_transport_lead_time, db_date_format, context=context)

            sol_values = {
                'product_id': pol.product_id and pol.product_id.id or False,
                'name': pol.name,
                'default_name': pol.default_name,
                'default_code': pol.default_code,
                'product_uom_qty': pol.product_qty,
                'product_uom': pol.product_uom and pol.product_uom.id or False,
                'product_uos_qty': pol.product_qty,
                'product_uos': pol.product_uom and pol.product_uom.id or False,
                'price_unit': price_unit_converted,
                'nomenclature_description': pol.nomenclature_description,
                'nomenclature_code': pol.nomenclature_code,
                'comment': pol.comment,
                'nomen_manda_0': pol.nomen_manda_0 and pol.nomen_manda_0.id or False,
                'nomen_manda_1': pol.nomen_manda_1 and pol.nomen_manda_1.id or False,
                'nomen_manda_2': pol.nomen_manda_2 and pol.nomen_manda_2.id or False,
                'nomen_manda_3': pol.nomen_manda_3 and pol.nomen_manda_3.id or False,
                'nomen_sub_0': pol.nomen_sub_0 and pol.nomen_sub_0.id or False,
                'nomen_sub_1': pol.nomen_sub_1 and pol.nomen_sub_1.id or False,
                'nomen_sub_2': pol.nomen_sub_2 and pol.nomen_sub_2.id or False,
                'nomen_sub_3': pol.nomen_sub_3 and pol.nomen_sub_3.id or False,
                'nomen_sub_4': pol.nomen_sub_4 and pol.nomen_sub_4.id or False,
                'nomen_sub_5': pol.nomen_sub_5 and pol.nomen_sub_5.id or False,
                'confirmed_delivery_date': line_confirmed,
                'sync_sourced_origin': pol.instance_sync_order_ref and pol.instance_sync_order_ref.name or False,
                'type': 'make_to_order',
            }
            if create_line:
                sol_values.update({
                    'order_id': so_id,
                    'date_planned': pol.date_planned,
                    'set_as_sourced_n': True,
                })
                sol_values.update(self.get_split_info(cr, uid, pol, context))
                new_sol = self.pool.get('sale.order.line').create(cr, uid, sol_values, context=context)
                self.write(cr, uid, [pol.id], {'linked_sol_id': new_sol}, context=context)
            else: # update FO line
                self.pool.get('sale.order.line').write(cr, uid, [pol.linked_sol_id.id], sol_values, context=context)

        return True


    def create_sol_from_pol(self, cr, uid, ids, fo_id, context=None):
        '''
        Method called when confirming a newly created PO line in a PO linked to a FO (normal flow)
        So we have to create the sale.order.line from the given purchase.order.line
        @param fo_id: id of sale.order (int)
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        if not fo_id:
            raise Exception, "No parent Sale Order given for the new Sale Order line"
        if isinstance(fo_id, list):
            fo_id = fo_id[0]

        sale_order = self.pool.get('sale.order').browse(cr, uid, fo_id, context=context)
        new_sol_id = False
        for pol in self.browse(cr, uid, ids, context=context):
            # convert from currency of pol to currency of sol
            price_unit_converted = self.pool.get('res.currency').compute(cr, uid, pol.currency_id.id, sale_order.currency_id.id, pol.price_unit or 0.0,
                                                                         round=False, context={'date': pol.order_id.date_order})

            if sale_order.order_type == 'regular' and price_unit_converted < 0.00001:
                price_unit_converted = 0.00001

            # date values
            ship_lt = self.pool.get('fields.tools').get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
            prep_lt = self.pool.get('fields.tools').get_field_from_company(cr, uid, object=self._name, field='preparation_lead_time', context=context)
            db_date_format = self.pool.get('date.tools').get_db_date_format(cr, uid, context=context)

            # compute confirmed date for line:
            line_confirmed = False
            if pol.confirmed_delivery_date:
                line_confirmed = self.pool.get('purchase.order').compute_confirmed_delivery_date(cr, uid, pol.order_id, pol.confirmed_delivery_date,
                                                                                                 prep_lt, ship_lt, sale_order.est_transport_lead_time, db_date_format, context=context)

            sol_values = {
                'order_id': fo_id,
                'product_id': pol.product_id and pol.product_id.id or False,
                'name': pol.name,
                'type': 'make_to_order',
                'default_name': pol.default_name,
                'default_code': pol.default_code,
                'product_uom_qty': pol.product_qty,
                'product_uom': pol.product_uom and pol.product_uom.id or False,
                'product_uos_qty': pol.product_qty,
                'product_uos': pol.product_uom and pol.product_uom.id or False,
                'price_unit': price_unit_converted,
                'nomenclature_description': pol.nomenclature_description,
                'nomenclature_code': pol.nomenclature_code,
                'comment': pol.comment,
                'nomen_manda_0': pol.nomen_manda_0 and pol.nomen_manda_0.id or False,
                'nomen_manda_1': pol.nomen_manda_1 and pol.nomen_manda_1.id or False,
                'nomen_manda_2': pol.nomen_manda_2 and pol.nomen_manda_2.id or False,
                'nomen_manda_3': pol.nomen_manda_3 and pol.nomen_manda_3.id or False,
                'nomen_sub_0': pol.nomen_sub_0 and pol.nomen_sub_0.id or False,
                'nomen_sub_1': pol.nomen_sub_1 and pol.nomen_sub_1.id or False,
                'nomen_sub_2': pol.nomen_sub_2 and pol.nomen_sub_2.id or False,
                'nomen_sub_3': pol.nomen_sub_3 and pol.nomen_sub_3.id or False,
                'nomen_sub_4': pol.nomen_sub_4 and pol.nomen_sub_4.id or False,
                'nomen_sub_5': pol.nomen_sub_5 and pol.nomen_sub_5.id or False,
                'confirmed_delivery_date': line_confirmed,
                'date_planned': (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d'),
                'sync_sourced_origin': pol.instance_sync_order_ref and pol.instance_sync_order_ref.name or False,
                'set_as_sourced_n': True,
            }
            # create FO line:
            sol_values.update(self.get_split_info(cr, uid, pol, context))
            new_sol_id = self.pool.get('sale.order.line').create(cr, uid, sol_values, context=context)

            # update current PO line:
            self.write(cr, uid, pol.id, {'link_so_id': fo_id, 'linked_sol_id': new_sol_id}, context=context)
        
        return new_sol_id


    def action_validated_n(self, cr, uid, ids, context=None):
        '''
        wkf method to validate the PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        self.write(cr, uid, ids, {'state': 'validated_n'}, context=context)

        # add line to parent SO if needed:
        for pol in self.browse(cr, uid, ids, context=context):
            parent_so_id = self.pool.get('sale.order').search(cr, uid, [
                ('name', '=', pol.origin),
                ('procurement_request', 'in', ['t', 'f']),
            ], context=context)
            if parent_so_id:
                new_sol_id = self.create_sol_from_pol(cr, uid, [pol.id], parent_so_id, context=context)
                # set the boolean "set_as_sourced_n" to True in order to trigger workflow transition draft => sourced_n:
                self.pool.get('sale.order.line').write(cr, uid, new_sol_id, {'set_as_sourced_n': True}, context=context)

        return True


    def action_validate(self, cr, uid, ids, context=None):
        '''
        wkf method to validate the PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        # check analytic distribution before validating the line:
        self.check_analytic_distribution(cr, uid, ids, context=context)

        # update FO lines:
        self.update_fo_lines(cr, uid, ids, context=context)
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'sourced_v', cr)

        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        return True


    def action_sourced_s(self, cr, uid, ids, context=None):
        '''
        wkf method when PO line get the sourced_s state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        self.write(cr, uid, ids, {'state': 'sourced_s'}, context=context)

        self.update_fo_lines(cr, uid, ids, context=context)
        # update linked sol (same instance) to sourced-s (if has)
        for po in self.browse(cr, uid, ids, context=context):
            if po.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', po.linked_sol_id.id, 'sourced_s', cr)

        return True
        
        
    def action_sourced_v(self, cr, uid, ids, context=None):
        '''
        wkf method when PO line get the sourced_v state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        self.write(cr, uid, ids, {'state': 'sourced_v'}, context=context)

        #update linked sol (same instance) to sourced-v (if has)
        for po in self.browse(cr, uid, ids, context=context):
            if po.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', po.linked_sol_id.id, 'sourced_v', cr)

        return True


    def action_sourced_n(self, cr, uid, ids, context=None):
        '''
        wkf method when PO line get the sourced_n state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'sourced_n'}, context=context)

        return True


    def action_confirmed(self, cr, uid, ids, context=None):
        '''
        wkf method to confirm the PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # Create IN lines
        po_obj = self.pool.get('purchase.order')
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        po_line_obj = self.pool.get('purchase.order.line')
        wf_service = netsvc.LocalService("workflow")

        # update FO line with change on PO line
        self.update_fo_lines(cr, uid, ids, context=context)

        for line in po_line_obj.browse(cr, uid, ids):
            # Search existing IN for PO line
            in_id = picking_obj.search(cr, uid, [
                ('purchase_id', '=', line.order_id.id),
                ('state', 'not in', ['done'])
            ])
            created = False
            if len(in_id) < 1:
                in_id = po_obj.create_picking(cr, uid, line.order_id, context)
                created = True
            else:
                in_id = in_id[0]
            move_id = po_obj.create_picking_line(cr, uid, in_id, line, context)
            if created:
                wf_service.trg_validate(uid, 'stock.picking', in_id, 'button_confirm', cr)
            else:
                move_obj.in_action_confirm(cr, uid, move_id, context)


            # if line created in PO, then create a FO line that match with it:
            if not line.linked_sol_id and line.origin:
                fo_id = self.update_origin_link(cr, uid, line.origin, context=context)
                fo_id = fo_id['link_so_id'] if fo_id else False
                if fo_id:
                    new_sol_id = self.create_sol_from_pol(cr, uid, line.id, fo_id, context=context)
                    self.write(cr, uid, line.id, {
                        'link_so_id': fo_id,
                        'linked_sol_id': new_sol_id,
                    }, context=context)
                    wf_service.trg_validate(uid, 'sale.order.line', new_sol_id, 'confirmed', cr)

            # Confirm FO line
            if line.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', line.linked_sol_id.id, 'confirmed', cr)

        self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

        # create or update the linked commitment voucher:
        self.create_or_update_commitment_voucher(cr, uid, ids, context=context)

        return True


    def action_done(self, cr, uid, ids, context=None):
        '''
        Workflow method called when POL is done
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        for pol in self.browse(cr, uid, ids, context=context):
            # if the PO line is linked to an internal IR line, then no PICK/OUT needed and we close the IR line:
            if pol.linked_sol_id and pol.linked_sol_id.procurement_request and pol.linked_sol_id.order_id.location_requestor_id.usage == 'internal':
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'done', cr)

        self.write(cr, uid, ids, {'state': 'done'}, context=context)

        return True


    def action_cancel(self, cr, uid, ids, context=None):
        '''
        Wkf method called when getting the cancel state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        # cancel the linked SO line too:
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'cancel', cr)

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

        return True


    def action_cancel_r(self, cr, uid, ids, context=None):
        '''
        Wkf method called when getting the cancel state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        # cancel the linked SO line too:
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'cancel_r', cr)

        self.write(cr, uid, ids, {'state': 'cancel_r'}, context=context)

        return True

purchase_order_line()


class purchase_order(osv.osv):
    _name = "purchase.order"
    _inherit = "purchase.order"


    def validate_lines(self, cr, uid, ids, context=None):
        """
        Force PO lines validation and update PO state
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        for po in self.browse(cr, uid, ids, context=context):
            for pol_id in [pol.id for pol in po.order_line]:
                wf_service.trg_validate(uid, 'purchase.order.line', pol_id, 'validated', cr)

        return True


    def confirm_lines(self, cr, uid, ids, context=None):
        """
        Confirming all lines of the PO
        validated -> confirmed
        """
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        for po in self.browse(cr, uid, ids, context=context):
            for pol_id in [pol.id for pol in po.order_line]:
                wf_service.trg_validate(uid, 'purchase.order.line', pol_id, 'confirmed', cr)

        return True


    def action_done(self, cr, uid, ids, context=None):
        """
        Done activity in workflow.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for order in self.read(cr, uid, ids, ['order_type'], context=context):
            vals = {'state': 'done'}
            if order['order_type'] == 'direct':
                vals.update({'shipped': 1})
            self.write(cr, uid, order['id'], vals, context=context)
        return True

purchase_order()
