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
                so_id = self.pool.get('sale.order').search(cr, uid, [
                    ('name', '=', pol.origin),
                    ('procurement_request', 'in', ['t', 'f']),
                ], context=context)
                if not so_id:
                    continue # no sale order linked to our PO line
                else:
                    so_id = so_id[0]
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
            }
            if create_line:
                sol_values.update({
                    'order_id': so_id,    
                    'date_planned': pol.date_planned,
                })
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

        self.write(cr, uid, ids, {'state': 'done'}, context=context)

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
            

    def wkf_picking_done(self, cr, uid, ids, context=None):
        '''
        Change the shipped boolean and the state of the PO
        '''
        direct_order_id_list = []
        other_id_list = []
        for order in self.read(cr, uid, ids, ['order_type'], context=context):
            if order['order_type'] == 'direct':
                direct_order_id_list.append(order['id'])
            else:
                other_id_list.append(order['id'])

        if direct_order_id_list:
            self.write(cr, uid, direct_order_id_list, {'state': 'approved'}, context=context)
        if other_id_list:
            self.write(cr, uid, other_id_list, {'shipped':1,'state':'approved'}, context=context)
        return True


    def wkf_confirm_order(self, cr, uid, ids, context=None):
        '''
        Update the confirmation date of the PO at confirmation.
        Check analytic distribution.
        '''
        # Objects
        po_line_obj = self.pool.get('purchase.order.line')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        todo = []
        reset_soq = []
        stopped_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'status_3')[1]
        for po in self.browse(cr, uid, ids, context=context):
            line_error = []
            if po.order_type == 'regular':
                cr.execute('SELECT line_number FROM purchase_order_line WHERE (price_unit*product_qty < 0.00001 OR price_unit = 0.00) AND order_id = %s', (po.id,))
                line_errors = cr.dictfetchall()
                for l_id in line_errors:
                    if l_id not in line_error:
                        line_error.append(l_id['line_number'])

            if len(line_error) > 0:
                errors = ' / '.join(str(x) for x in line_error)
                raise osv.except_osv(_('Error !'), _('You cannot have a purchase order line with a 0.00 Unit Price or 0.00 Subtotal. Lines in exception : %s') % errors)

            # Check if there is a temporary product in the purchase order :
            temp_prod_ids = product_obj.search(cr, uid, [('international_status', '=', 5)], context=context)
            line_with_temp_ids = po_line_obj.search(cr, uid, [('order_id', '=', po.id), ('product_id', 'in', temp_prod_ids)], context=context)
            line_err = " / ".join([str(l.line_number) for l in po_line_obj.browse(cr, uid, line_with_temp_ids, context=context)])

            if line_with_temp_ids:
                raise osv.except_osv(
                    _("Warning"),
                    _("You cannot confirm purchase order containing temporary product (line: %s)") % line_err,
                )


            # Check if the pricelist of the order is good according to currency of the partner
            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid,
                                                                      [('in_search', '=', po.partner_id.partner_type)],
                                                                      order='NO_ORDER', context=context)
            if po.pricelist_id.id not in pricelist_ids:
                raise osv.except_osv(_('Error'), _('The currency used on the order is not compatible with the supplier. Please change the currency to choose a compatible currency.'))

            if not po.split_po and not po.order_line:
                raise osv.except_osv(_('Error !'), _('You can not validate a purchase order without Purchase Order Lines.'))

            if po.order_type == 'purchase_list' and po.amount_total == 0:  # UFTP-69
                raise osv.except_osv(_('Error'), _('You can not validate a purchase list with a total amount of 0.'))

            for line in po.order_line:
                if line.state=='draft':
                    todo.append(line.id)
                if line.soq_updated:
                    reset_soq.append(line.id)

                # check if the current product is stopped or not : If the PO was created by Sync. engine, do not check
                if not po.push_fo and line.product_id and line.product_id.state and line.product_id.state.id == stopped_id:
                    raise osv.except_osv(_('Error'), _('You can not validate a PO with stopped products (line %s).') % (line.line_number, ))

            message = _("Purchase order '%s' is validated.") % (po.name,)
            self.log(cr, uid, po.id, message)
            self.infolog(cr, uid, "Purchase order id:%s (%s) is validated." % (
                po.id, po.name,
            ))
            # hook for corresponding Fo update
            self._hook_confirm_order_update_corresponding_so(cr, uid, ids, context=context, po=po)

        po_line_obj.action_confirm(cr, uid, todo, context)
        po_line_obj.write(cr, uid, reset_soq, {'soq_updated': False,}, context=context)

        self.write(cr, uid, ids, {'state' : 'confirmed',
                                  'validator' : uid,
                                  'date_confirm': time.strftime('%Y-%m-%d')}, context=context)

        self.ssl_products_in_line(cr, uid, ids, context=context)
        self.check_analytic_distribution(cr, uid, ids, context=context)

        return True


    def common_code_from_wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        delivery confirmed date at po level is mandatory
        update corresponding date at line level if needed.
        Check analytic distribution
        Check that no line have a 0 price unit.
        '''
        # Objects
        po_line_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Check analytic distribution
        self.check_analytic_distribution(cr, uid, ids, context=context)
        for po in self.read(cr, uid, ids, ['order_type', 'state', 'delivery_confirmed_date'], context=context):
            # prepare some values
            is_regular = po['order_type'] == 'regular' # True if order_type is regular, else False
            line_error = []
            # msf_order_date checks
            if po['state'] == 'approved' and not po['delivery_confirmed_date']:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            # for all lines, if the confirmed date is not filled, we copy the header value
            if is_regular:
                cr.execute('SELECT line_number FROM purchase_order_line WHERE (price_unit*product_qty < 0.00001 OR price_unit = 0.00) AND order_id = %s', (po['id'],))
                line_errors = cr.dictfetchall()
                for l_id in line_errors:
                    if l_id not in line_error:
                        line_error.append(l_id['line_number'])

            if len(line_error) > 0:
                errors = ' / '.join(str(x) for x in line_error)
                raise osv.except_osv(_('Error !'), _('You cannot have a purchase order line with a 0.00 Unit Price or 0.00 Subtotal. Lines in exception : %s') % errors)

            lines_to_update = po_line_obj.search(
                cr, uid,
                [('order_id', '=', po['id']), ('confirmed_delivery_date', '=', False)],
                order='NO_ORDER',
                context=context)

            po_line_obj.write(cr, uid, lines_to_update, {'confirmed_delivery_date': po['delivery_confirmed_date']}, context=context)
        # MOVE code for COMMITMENT into wkf_approve_order
        return True


    def wkf_confirm_wait_order(self, cr, uid, ids, context=None):
        """
        Checks:
        1/ if all purchase line could take an analytic distribution
        2/ if a commitment voucher should be created after PO approbation

        _> originally in purchase.py from analytic_distribution_supply

        Checks if the Delivery Confirmed Date has been filled

        _> originally in order_dates.py from msf_order_date
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        sol_obj = self.pool.get('sale.order.line')
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        so_obj =  self.pool.get('sale.order')
        product_obj = self.pool.get('product.product')
        po_line_obj = self.pool.get('purchase.order.line')

        # Check if there is a temporary product in the purchase order :
        for po in self.browse(cr, uid, ids, context=context):
            temp_prod_ids = product_obj.search(cr, uid, [('international_status', '=', 5)], context=context)
            line_with_temp_ids = po_line_obj.search(cr, uid, [('order_id', '=', po.id), ('product_id', 'in', temp_prod_ids)], context=context)
            line_err = " / ".join([str(l.line_number) for l in po_line_obj.browse(cr, uid, line_with_temp_ids, context=context)])

            if line_with_temp_ids:
                raise osv.except_osv(
                    _("Warning"),
                    _("You cannot confirm purchase order containing temporary product (line: %s)") % line_err,
                )

        # Create extra lines on the linked FO/IR
        self.create_extra_lines_on_fo(cr, uid, ids, context=context)

        # code from wkf_approve_order
        self.common_code_from_wkf_approve_order(cr, uid, ids, context=context)
        # set the state of purchase order to confirmed_wait
        self.write(cr, uid, ids, {'state': 'confirmed_wait'}, context=context)
        sol_ids = self.get_sol_ids_from_po_ids(cr, uid, ids, context=context)

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context, sol_ids=sol_ids)
        # UF-2509: so_ids is a list, not an int
        exp_sol_ids = exp_sol_obj.search(cr, uid, [('order_id', 'in', so_ids)], context=context)
        # from so, list corresponding po
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        for exp_sol in exp_sol_obj.read(cr, uid, exp_sol_ids, ['po_id'], context=context):
            # UFTP-335: Added a check in if to avoid False value being taken
            if exp_sol['po_id'] and exp_sol['po_id'][0] not in all_po_ids:
                all_po_ids.append(exp_sol['po_id'][0])
        ids_to_read = all_po_ids[:]
        if ids[0] in ids_to_read:
            ids_to_read.remove(ids[0])
        if ids_to_read:
            list_po_name = ', '.join([linked_po['name'] for linked_po in self.read(cr, uid, ids_to_read, ['name'], context)])
            self.log(cr, uid, ids[0], _("The order %s is in confirmed (waiting) state and will be confirmed once the related orders [%s] would have been confirmed"
                                        ) % (self.read(cr, uid, ids[0], ['name'])['name'], list_po_name))

        # !!BEWARE!! we must update the So lines before any writing to So objects
        for po in self.browse(cr, uid, ids, context=context):
            # hook for corresponding Fo update
            context['wait_order'] = True
            self._hook_confirm_order_update_corresponding_so(cr, uid, ids, context=context, po=po, so_ids=so_ids)
            del context['wait_order']
            self.infolog(cr, uid, "The PO id:%s (%s) has been confirmed" % (po.id, po.name))

        # sale order lines with modified state
        if sol_ids:
            sol_obj.write(cr, uid, sol_ids, {'state': 'confirmed'}, context=context)

        return True


    def wkf_confirm_trigger(self, cr, uid, ids, context=None):
        '''
        trigger corresponding so then po
        '''
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        so_obj = self.pool.get('sale.order')
        wf_service = netsvc.LocalService("workflow")

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        # from so, list corresponding po first level
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        # from listed po, list corresponding so
        all_so_ids = self.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)
        # from all so, list all corresponding po second level
        all_po_for_all_so_ids = so_obj.get_po_ids_from_so_ids(cr, uid, all_so_ids, context=context)

        not_confirmed_po = self.search(cr, uid, [
            ('id', 'not in', all_po_for_all_so_ids),
            ('state', '=', 'confirmed_wait'),
        ], context=context)

        # we trigger all the corresponding sale order -> test_lines is called on these so
        for so_id in all_so_ids:
            wf_service.trg_write(uid, 'sale.order', so_id, cr)

        # US-1765: PO linked to multiple POs, last PO confirmed
        # wkf_confirm_trigger is called for this PO and after again and again and again for each linked POs (by the workflow)
        # register the first call by setting po_confirmed=True and do not process the others
        confirmed = False
        if all_po_for_all_so_ids:
            # if one PO is not confirmed_/wait we can do all the stuff
            if not self.search_exist(cr, uid,
                                     [('id', 'in', all_po_for_all_so_ids), ('state', 'not in', ['approved', 'confirmed_wait'])],
                                     context=context):
                confirmed = self.search_exist(cr, uid,
                                              [('id', 'in', all_po_for_all_so_ids), ('po_confirmed', '=', True)], context=context)
        if confirmed:
            # one of the linked PO has already triggered this method for all POs, so we can stop
            return True
        if ids:
            # register the call
            # direct sql to not trigger (again) the workflow
            cr.execute('''update purchase_order set po_confirmed='t' where id in %s and state = 'confirmed_wait' ''', (tuple(ids),))

        # we trigger pos of all sale orders -> all_po_confirm is called on these po
        for po_id in all_po_for_all_so_ids:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        for po_id in not_confirmed_po:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        return True


    def wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        Checks if the invoice should be create from the purchase order
        or not
        If the PO is a DPO, set all related OUT stock move to 'done' state
        '''
        line_obj = self.pool.get('purchase.order.line')
        so_line_obj = self.pool.get('sale.order.line')
        move_obj = self.pool.get('stock.move')
        uf_config = self.pool.get('unifield.setup.configuration')
        wf_service = netsvc.LocalService("workflow")
        imd_obj = self.pool.get('ir.model.data')

        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}

        # duplicated code with wkf_confirm_wait_order because of backward compatibility issue with yml tests for dates,
        # which doesnt execute wkf_confirm_wait_order (null value in column "date_expected" violates not-null constraint for stock.move otherwise)
        # msf_order_date checks
        self.common_code_from_wkf_approve_order(cr, uid, ids, context=context)

        setup = uf_config.get_config(cr, uid)

        for order in self.browse(cr, uid, ids):
            if order.order_type == 'purchase_list' and order.amount_total == 0:  # UFTP-69
                # total amount could be set to 0 after it was Validated
                # or no lines
                # (after wkf_confirm_order total amount check)
                raise osv.except_osv(_('Error'), _('You can not confirm a purchase list with a total amount of 0.'))

            # Create commitments for each PO only if po is "from picking"
            # UTP-114: No Commitment Voucher on PO that are 'purchase_list'!
            if (order.invoice_method in ['picking', 'order'] and not order.from_yml_test and order.order_type not in ['in_kind', 'purchase_list'] and order.partner_id.partner_type != 'intermission') or (order.invoice_method == 'manual' and order.order_type == 'direct' and order.partner_id.partner_type == 'esc'):
                # UTP-827: no commitment if they are imported for ESC partners
                if not (order.partner_id.partner_type == 'esc' and setup.import_commitments):
                    # US-917: Check if any CV exists for the given PO
                    commit_obj = self.pool.get('account.commitment')
                    if not commit_obj.search_exist(cr, uid,
                                                   [('purchase_id', 'in', [order.id])], context=context):
                        self.action_create_commitment(cr, uid, [order.id], order.partner_id and order.partner_id.partner_type, context=context)
            todo = []
            todo2 = []
            todo3 = []
            todo4 = {}
            to_invoice = set()
            if order.partner_id.partner_type in ('internal', 'esc') and order.order_type == 'regular' or \
                    order.order_type in ['donation_exp', 'donation_st', 'loan']:
                self.write(cr, uid, [order.id], {'invoice_method': 'manual'})
                line_obj.write(cr, uid, [x.id for x in order.order_line], {'invoiced': 1})

            message = _("Purchase order '%s' is confirmed.") % (order.name,)
            self.log(cr, uid, order.id, message)

            if order.order_type == 'direct':
                if order.partner_id.partner_type != 'esc':
                    self.write(cr, uid, [order.id], {'invoice_method': 'order'}, context=context)
                for line in order.order_line:
                    if line.procurement_id:
                        todo.append(line.procurement_id.id)
                        todo4.update({line.procurement_id.id: line.id})

            if todo:
                todo2 = so_line_obj.search(cr, uid, [('procurement_id', 'in', todo)], order='NO_ORDER', context=context)

            if todo2:
                sm_ids = move_obj.search(cr, uid, [('sale_line_id', 'in', todo2)], context=context)
                move_obj.action_confirm(cr, uid, sm_ids, context=context)
                stock_location_id = imd_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
                cross_id = imd_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
                non_stock_id = imd_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
                for move in move_obj.browse(cr, uid, sm_ids, context=context):
                    # Reset the location_id to Stock
                    location_id = stock_location_id
                    # Search if this move has been processed
                    backmove_exist = move_obj.search_exist(cr, uid,
                                                           [('backmove_id', '=', move.id)])
                    if move.state != 'done' and not backmove_exist and not move.backmove_id:
                        if move.product_id.type in ('service', 'service_recep'):
                            location_id = cross_id
                        elif move.product_id.type == 'consu':
                            location_id = non_stock_id
                        move_obj.write(cr, uid, [move.id], {'dpo_id': order.id,
                                                            'state': 'done',
                                                            'dpo_line_id': todo4.get(move.sale_line_id.procurement_id.id, False),
                                                            'location_id': location_id,
                                                            'location_dest_id': location_id,
                                                            'date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
                        wf_service.trg_trigger(uid, 'stock.move', move.id, cr)
                        if move.picking_id:
                            if move.picking_id.sale_id:
                                sale = move.picking_id.sale_id
                                if sale.partner_id.partner_type in ('section', 'intermission') and sale.invoice_quantity == 'procurement':
                                    to_invoice.add(move.picking_id.id)
                            all_move_closed = True
                            # Check if the picking should be updated
                            if move.picking_id.subtype == 'picking':
                                for m in move.picking_id.move_lines:
                                    if m.id not in sm_ids and m.state != 'done':
                                        all_move_closed = False
                                        break
                            # If all stock moves of the picking is done, trigger the workflow
                            if all_move_closed:
                                todo3.append(move.picking_id.id)

            if todo3:
                for pick_id in todo3:
                    wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
                    wf_service.trg_write(uid, 'stock.picking', pick_id, cr)

            if to_invoice:
                conf_context = context.copy()
                conf_context['invoice_dpo_confirmation'] = order.id
                self.pool.get('stock.picking').action_invoice_create(cr, uid, list(to_invoice), type='out_invoice', context=conf_context)

        # @@@override@purchase.purchase.order.wkf_approve_order
        self.write(cr, uid, ids, {'state': 'approved', 'date_approve': time.strftime('%Y-%m-%d')})
        return True


    def wkf_action_cancel_po(self, cr, uid, ids, context=None):
        """
        Cancel activity in workflow.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        line_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                line_ids.append(line.id)
                if line.procurement_id and line.procurement_id.move_id:
                    self.pool.get('stock.move').write(cr, uid, line.procurement_id.move_id.id, {'state': 'cancel'}, context=context)
                    if line.procurement_id.move_id.picking_id:
                        wf_service.trg_write(uid, 'stock.picking', line.procurement_id.move_id.picking_id.id, cr)

        self.pool.get('purchase.order.line').cancel_sol(cr, uid, line_ids, context=context)
        return self.write(cr, uid, ids, {'state':'cancel'}, context=context)


    def wkf_confirm_cancel(self, cr, uid, ids, context=None):
        """
        Continue the workflow if all other POs are confirmed
        """
        wf_service = netsvc.LocalService("workflow")
        so_obj = self.pool.get('sale.order')

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        # from so, list corresponding po first level
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        # from listed po, list corresponding so
        all_so_ids = self.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)
        # from all so, list all corresponding po second level
        all_po_for_all_so_ids = so_obj.get_po_ids_from_so_ids(cr, uid, all_so_ids, context=context)

        not_confirmed_po = self.search(cr, uid, [
            ('id', 'not in', all_po_for_all_so_ids),
            ('state', '=', 'confirmed_wait'),
        ], context=context)

        # we trigger all the corresponding sale order -> test_lines is called on these so
        for so_id in all_so_ids:
            wf_service.trg_write(uid, 'sale.order', so_id, cr)

        # we trigger pos of all sale orders -> all_po_confirm is called on these po
        for po_id in all_po_for_all_so_ids:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        for po_id in not_confirmed_po:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

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
