# -*- coding: utf-8 -*-

from osv import osv
import netsvc
from tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
from msf_button_access_rights.osv_override import fakeUid


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


    def check_if_stock_take_date_with_esc_partner(self, cr, uid, ids, context=None):
        """
        Check if the PO line have a date of stock take with an ESC Partner
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for pol in self.browse(cr, uid, ids, context=context):
            if pol.order_id.partner_type == 'esc':
                if not pol.stock_take_date:
                    raise osv.except_osv(_('Warning !'), _('The Date of Stock Take is required for a Purchase Order if the Partner is an ESC.'))

        return True

    def check_and_update_original_line_at_split_cancellation(self, cr, uid, ids, context=None):
        '''
        Check if we are in case we must update original line, because line has been split and cancelled
        E.g: FO(COO) -> PO ext(COO) -> IN line partial cancel
                => then we must update PO (PROJ) line with new product qty (= original qty - cancelled qty)
        If yes, then we update PO line, IN and SYS-INT with new qty
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return True


    def cancel_related_in_moves(self, cr, uid, ids, context=None):
        '''
        check if PO line has related IN moves, if it is the case, then cancel them
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for pol in self.browse(cr, uid, ids, context=context):
            related_in_moves = self.pool.get('stock.move').search(cr, uid, [
                ('purchase_line_id', '=', pol.id),
                ('type', '=', 'in'),
                ('state', 'not in', ['done', 'cancel']),
            ], context=context)
            if related_in_moves:
                self.pool.get('stock.move').action_cancel(cr, uid, related_in_moves, context=context)

        return True


    def check_unit_price(self, cr, uid, ids, context=None):
        '''
        made some checks on unit price before validating the PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for pol in self.browse(cr, uid, ids, fields_to_fetch=['price_unit'], context=context):
            if not pol.price_unit:
                raise osv.except_osv(_('Warning'), _('You cannot validate a PO line with 0.0 as price unit !'))

        return True

    def update_fo_lines(self, cr, uid, ids, context=None, qty_updated=False, for_claim=False):
        '''
        update corresponding FO lines in the same instance
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        context['from_back_sync'] = True
        for pol in self.browse(cr, uid, ids, context=context):
            to_trigger = False
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
                    continue  # no sale order linked to our PO line
                sale_order = self.pool.get('sale.order').browse(cr, uid, so_id, context=context)
                if sale_order.state == 'cancel' and sale_order.procurement_request:
                    to_trigger = True
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

            line_stock_take = False
            if pol.stock_take_date:
                line_stock_take = pol.stock_take_date

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
                'stock_take_date': line_stock_take,
                'sync_sourced_origin': pol.instance_sync_order_ref and pol.instance_sync_order_ref.name or False,
                'type': 'make_to_order',
                'is_line_split': pol.is_line_split,
                'original_line_id': pol.original_line_id.linked_sol_id.id if pol.original_line_id else False,
            }

            # update modification comment if it is set
            if pol.modification_comment:
                sol_values['modification_comment'] = pol.modification_comment


            ad_id = pol.analytic_distribution_id or pol.order_id.analytic_distribution_id
            if create_line:
                sol_values.update({
                    'order_id': so_id,
                    'date_planned': pol.date_planned,
                })
                sol_values.update(self.get_split_info(cr, uid, pol, context))
                if not sol_values.get('is_line_split'):
                    sol_values['set_as_sourced_n'] = True
                # update analytic distribution if PO line has one
                if ad_id and not sale_order.procurement_request:
                    sol_values['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid,
                                                                                                         ad_id.id, {'partner_type': sale_order.partner_type}, context=context)
                if pol.created_by_sync:
                    sol_values['created_by_sync'] = True
                new_sol = self.pool.get('sale.order.line').create(cr, uid, sol_values, context=context)
                self.write(cr, uid, [pol.id], {'linked_sol_id': new_sol}, context=context)

                if to_trigger:
                    # IR is cancel but a new line is added, trigger a new wkf
                    # UC: IR > PO > FO (full claim retrun + replacement on IN)
                    cr.execute("update sale_order set state='draft' where id=%s", (so_id,))

                # if OUT move already exists for this sale.order.line, then the split going to be created must be linked to
                # the right OUT move (moves are already splits at this level):
                if sol_values['is_line_split']:
                    netsvc.LocalService('workflow').trg_validate(uid, 'sale.order.line', new_sol, 'sourced', cr)
                    linked_out_moves = self.pool.get('stock.move').search(cr, uid, [
                        ('sale_line_id', '=', sol_values['original_line_id']),
                        ('type', '=', 'out')],
                        context=context)
                    if len(linked_out_moves) > 1:
                        for out_move in self.pool.get('stock.move').browse(cr, uid, linked_out_moves, context=context):
                            if out_move.state in ('assigned', 'confirmed') and out_move.product_qty == sol_values['product_uom_qty']:
                                self.pool.get('stock.move').write(cr, uid, [out_move.id], {'sale_line_id': new_sol}, context=context)

            else:  # update FO line
                if pol.linked_sol_id and not pol.linked_sol_id.analytic_distribution_id and not pol.linked_sol_id.order_id.analytic_distribution_id and ad_id and not sale_order.procurement_request:
                    sol_values['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid,
                                                                                                         ad_id.id, {'partner_type': sale_order.partner_type}, context=context)
                # don't change this values if exists on sol:
                if pol.linked_sol_id.is_line_split:
                    sol_values.pop('is_line_split')
                if pol.linked_sol_id.original_line_id:
                    sol_values.pop('original_line_id')
                if pol.linked_sol_id.state == 'confirmed' and 'product_uom_qty' in sol_values and sol_values['product_uom_qty'] != pol.linked_sol_id.product_uom_qty:
                    linked_out_moves = self.pool.get('stock.move').search(cr, uid, [
                        ('sale_line_id', '=', pol.linked_sol_id.id),
                        ('type', '=', 'out'),
                        ('state', 'in', ['assigned', 'confirmed']),
                        ('product_qty', '=',  pol.linked_sol_id.product_uom_qty)
                    ], context=context)
                    if linked_out_moves:
                        self.pool.get('stock.move').write(cr, uid, [linked_out_moves[0]], {'product_qty': sol_values['product_uom_qty'], 'product_uos_qty': sol_values['product_uom_qty']}, context=context)
                    elif for_claim:
                        # if claim created but IR already confirmed, if qty can't be decreased on OUT because OUT was split, cancel the qty related to the claim
                        linked_out_moves = self.pool.get('stock.move').search(cr, uid, [
                            ('sale_line_id', '=', pol.linked_sol_id.id),
                            ('type', '=', 'out'),
                            ('state', 'in', ['assigned', 'confirmed']),
                            ('product_qty', '=',  for_claim)
                        ], context=context)
                        if linked_out_moves:
                            self.pool.get('stock.move').write(cr, uid, [linked_out_moves[0]], {'sale_line_id': False}, context=context)
                            self.pool.get('stock.move').action_cancel(cr, uid, [linked_out_moves[0]], context=context)

                self.pool.get('sale.order.line').write(cr, uid, [pol.linked_sol_id.id], sol_values, context=context)
                if qty_updated:
                    # if FO line qty reduced by a Cancel(/R) on IN, trigger update to PO proj line
                    rule_obj = self.pool.get('sync.client.message_rule')
                    rule_obj._manual_create_sync_message(cr, uid, 'sale.order.line', pol.linked_sol_id.id, {},
                                                         'purchase.order.line.sol_update_original_pol', rule_obj._logger, check_identifier=False, context=context)

        context['from_back_sync'] = False

        return True


    def create_sol_from_pol(self, cr, uid, ids, fo_id, context=None):
        '''
        Method called when confirming a newly created PO line in a PO linked to a FO (normal flow)
        So we have to create the sale.order.line from the given purchase.order.line
        @param fo_id: id of sale.order (int)
        '''

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not fo_id:
            raise Exception, "No parent Sale Order given for the new Sale Order line"
        if isinstance(fo_id, list):
            fo_id = fo_id[0]

        context['from_back_sync'] = True
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

            line_stock_take = False
            if pol.stock_take_date:
                line_stock_take = pol.stock_take_date

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
                'stock_take_date': line_stock_take,
                'date_planned': (datetime.now() + relativedelta(days=+2)).strftime('%Y-%m-%d'),
                'sync_sourced_origin': pol.instance_sync_order_ref and pol.instance_sync_order_ref.name or False,
                'set_as_sourced_n': True,
            }

            if pol.resourced_original_line:
                # pol resourced, set orginal line on new line
                sol_values['resourced_original_line'] = pol.resourced_original_line.linked_sol_id and pol.resourced_original_line.linked_sol_id.id or False
                sol_values['resourced_original_remote_line'] = pol.resourced_original_line.linked_sol_id and pol.resourced_original_line.linked_sol_id.sync_linked_pol or False
            # if PO line has an analytic distribution, we copy it
            ad_id = pol.analytic_distribution_id or pol.order_id.analytic_distribution_id
            if ad_id and not sale_order.procurement_request:
                sol_values.update({
                    'analytic_distribution_id': self.pool.get('analytic.distribution').
                    copy(cr, uid, ad_id.id, {'partner_type': sale_order.partner_type},
                         context=context)
                })
            # create FO line:
            sol_values.update(self.get_split_info(cr, uid, pol, context))
            new_sol_id = self.pool.get('sale.order.line').create(cr, uid, sol_values, context=context)

            # update current PO line:
            self.write(cr, uid, pol.id, {'link_so_id': fo_id, 'linked_sol_id': new_sol_id}, context=context)

        context['from_back_sync'] = False
        return new_sol_id


    def create_sys_int(self, cr, uid, ids, context=None):
        '''
        create system internal (SYS-INT) picking object
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not ids:
            raise Exception, "No PO line given"

        # load common data into context:
        self.pool.get('data.tools').load_common_data(cr, uid, ids, context=context)

        # create INT:
        pol = self.browse(cr, uid, ids, context=context)[0]
        name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.system.internal')
        pick_values = {
            'name': name,
            'origin': pol.order_id.origin and '%s:%s' % (pol.order_id.name, pol.order_id.origin) or pol.order_id.name,
            'type': 'internal',
            'subtype': 'sysint',
            'state': 'draft',
            'sale_id': False,
            'purchase_id': pol.order_id.id,
            'address_id': False,
            'date': context['common']['date'],
            'company_id': context['common']['company_id'],
            'reason_type_id': self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1],
        }
        pick_id = self.pool.get('stock.picking').create(cr, uid, pick_values, context=context)

        # log picking creation
        self.pool.get('stock.picking').log(cr, uid, pick_id, _('The new internal Picking %s has been created.') % name)

        return pick_id

    def create_counterpart_fo_for_external_partner_po(self, cr, uid, p_order, context=False):
        '''
        US-4165 : Create a Field Order as a loan Purchase Order's counterpart
        '''
        if context is None:
            context = {}

        company_obj = self.pool.get('res.company')
        curr_obj = self.pool.get('res.currency')
        pricelist_obj = self.pool.get('product.pricelist')

        pol_ids = self.search(cr, uid, [('order_id', '=', p_order.id), ('state', 'not in', ['cancel', 'cancel_r'])],
                              context=context)
        company_currency_id = company_obj.browse(cr, uid, uid, fields_to_fetch=['currency_id'], context=context).currency_id.id
        pricelist_id = pricelist_obj.search(cr, uid, [('currency_id', '=', company_currency_id), ('type', '=', 'sale')],
                                            context=context)[0]
        ftf = ['product_id', 'price_unit', 'product_uom', 'product_qty']
        counterpart_data = {
            'order_type': 'loan',
            'categ': p_order.categ,
            'origin': p_order.name,
            'loan_id': p_order.id,
            'loan_duration': p_order.loan_duration,
            'is_a_counterpart': True,
            'partner_id': p_order.partner_id.id,
            'partner_order_id': p_order.partner_id.address[0].id,
            'partner_shipping_id': p_order.partner_id.address[0].id,
            'partner_invoice_id': p_order.partner_id.address[0].id,
            'pricelist_id': pricelist_id,
            'order_line': [(0, 0, {
                'product_id': x.product_id.id,
                'price_unit': curr_obj.compute(cr, uid, p_order.pricelist_id.currency_id.id, company_currency_id,
                                               x.price_unit, round=False, context=context),
                'product_uom': x.product_uom.id,
                'product_uom_qty': x.product_qty,
                'type': 'make_to_stock',
            }) for x in self.browse(cr, uid, pol_ids, fields_to_fetch=ftf, context=context)],
        }

        return self.pool.get('sale.order').create(cr, uid, counterpart_data, context=context)

    def button_confirmed(self, cr, uid, ids, context=None):
        '''
        Method called when trying to confirm a PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        open_wizard = False
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.order_id.partner_id.partner_type in ('internal', 'section', 'intermission'):
                open_wizard = True
            if pol.state == 'validated_n':
                # if line is 'validated_n', pass through 'validated' state to ensure no checks has been missed
                #self.check_origin_is_set(self, cr, uid, pol, context=context)
                wf_service.trg_validate(uid, 'purchase.order.line', pol.id, 'validated', cr)

        if open_wizard:
            context.update({'pol_ids_to_confirm': ids})
            wiz_id = self.pool.get('purchase.order.line.manually.confirmed.wizard').create(cr, uid, {'pol_to_confirm': ids[0]}, context=context)
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'purchase_line_manually_confirmed_form_view')[1]

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order.line.manually.confirmed.wizard',
                'res_id': wiz_id,
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'target': 'new',
                'context': context
            }

        for pol_id in ids:
            wf_service.trg_validate(uid, 'purchase.order.line', pol_id, 'confirmed', cr)

        # Create the counterpart FO to a loan PO with an external partner if non-cancelled lines have been confirmed
        p_order = False
        for pol in self.browse(cr, uid, ids, context=context):
            p_order = pol.order_id
            break
        if p_order and p_order.order_type == 'loan' and not p_order.is_a_counterpart\
                and p_order.partner_type == 'external' and p_order.state == 'confirmed':
            self.create_counterpart_fo_for_external_partner_po(cr, uid, p_order, context=context)

        return True

    def action_validated_n(self, cr, real_uid, ids, context=None):
        '''
        wkf method to validate the PO line
        '''

        if real_uid == 1:
            uid = real_uid
        else:
            uid = fakeUid(1, real_uid)

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.write(cr, uid, ids, {'state': 'validated_n'}, context=context)

        # add line to parent SO if needed:
        for pol in self.browse(cr, uid, ids, context=context):
            if not pol.created_by_sync:
                parent_so_id = self.pool.get('sale.order').search(cr, uid, [
                    ('name', '=', pol.origin),
                    ('procurement_request', 'in', ['t', 'f']),
                ], context=context)
                if parent_so_id:
                    new_sol_id = self.create_sol_from_pol(cr, uid, [pol.id], parent_so_id, context=context)
                    # set the boolean "set_as_sourced_n" to True in order to trigger workflow transition draft => sourced_n:
                    self.pool.get('sale.order.line').write(cr, uid, new_sol_id, {'set_as_sourced_n': True}, context=context)

        return True

    def check_po_tax(self, cr, uid, ids, context=None):
        """
        Prevents from validating a PO with taxes when using an Intermission or Intersection partner
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for po_line in self.browse(cr, uid, ids, fields_to_fetch=['order_id', 'taxes_id'], context=context):
            if po_line.taxes_id and po_line.order_id.partner_type in ('intermission', 'section'):
                raise osv.except_osv(_('Error'), _("Taxes are forbidden with Intermission and Intersection partners."))

    def check_origin_for_validation(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        to_complete_ids = self.search(cr, uid, [('id', '=', ids), ('from_fo', '=', True), ('origin', '=', False), ('sync_linked_sol', '=', False)])
        if to_complete_ids:
            error = []
            for line in self.read(cr, uid, to_complete_ids, ['line_number', 'default_code'], context=context):
                error.append(_('#%d  %s') % (line['line_number'], line['default_code']))
            if len(error) == 1:
                raise osv.except_osv(_('Error'), _("This cannot be validated as line source document information is missing: %s") % error[0])
            else:
                raise osv.except_osv(_('Error'), _("These lines cannot be validated as line source document information is missing: \n - %s") % "\n -".join(error))

        return True

    def action_validate(self, cr, uid, ids, context=None):
        '''
        wkf method to validate the PO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        # checks before validating the line:
        self.check_origin_for_validation(cr, uid, ids, context=context)
        self.check_analytic_distribution(cr, uid, ids, context=context)
        self.check_if_stock_take_date_with_esc_partner(cr, uid, ids, context=context)
        self.check_unit_price(cr, uid, ids, context=context)
        self.check_po_tax(cr, uid, ids, context=context)

        # update FO lines:
        self.update_fo_lines(cr, uid, ids, context=context)
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.product_qty*pol.price_unit >= self._max_amount:
                raise osv.except_osv(_('Error'), _('%s, line %s: %s') % (pol.order_id.name, pol.line_number, _(self._max_msg)))

            if pol.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'sourced_v', cr)
            # update original qty, unit price, uom and currency on line level
            # doesn't update original qty and uom if already set (from IR)
            line_update = {
                'original_price': pol.price_unit,
                'original_currency_id': pol.currency_id.id
            }

            if not pol.original_product:
                line_update['original_product'] = pol.product_id.id

            if not pol.original_qty:
                line_update['original_qty'] = pol.product_qty

            if not pol.original_uom:
                line_update['original_uom'] = pol.product_uom.id

            self.write(cr, uid, pol.id, line_update, context=context)


        self.write(cr, uid, ids, {'state': 'validated', 'validation_date': datetime.now().strftime('%Y-%m-%d')}, context=context)

        return True


    def action_sourced_sy(self, cr, uid, ids, context=None):
        '''
        wkf method when PO line get the sourced_sy state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        self.write(cr, uid, ids, {'state': 'sourced_sy'}, context=context)

        self.update_fo_lines(cr, uid, ids, context=context)
        # update linked sol (same instance) to sourced-sy (if has)
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'sourced_sy', cr)

        return True


    def action_sourced_v(self, cr, uid, ids, context=None):
        '''
        wkf method when PO line get the sourced_v state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        self.write(cr, uid, ids, {'state': 'sourced_v'}, context=context)

        # update linked sol (same instance) to sourced-v (if has)
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
        if isinstance(ids, (int, long)):
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

        wf_service = netsvc.LocalService("workflow")

        # check before confirming the line:
        self.check_analytic_distribution(cr, uid, ids, context=context)
        self.check_if_stock_take_date_with_esc_partner(cr, uid, ids, context=context)

        # update FO line with change on PO line
        self.update_fo_lines(cr, uid, ids, context=context)

        pol_to_invoice = {}

        for pol in self.browse(cr, uid, ids):
            if not pol.confirmed_delivery_date:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))

            if not pol.product_id and pol.linked_sol_id and not pol.linked_sol_id.order_id.procurement_request:
                # PO nomen (PROJ) => FO (nomen COO)
                raise osv.except_osv(_('Error'), _('Line %s: Please choose a product before confirming the line') % pol.line_number)

            if pol.order_type != 'direct' and not pol.from_synchro_return_goods:
                # create incoming shipment (IN):
                in_id = self.pool.get('stock.picking').search(cr, uid, [
                    ('purchase_id', '=', pol.order_id.id),
                    ('state', 'not in', ['done', 'cancel', 'shipped', 'updated', 'import']),
                    ('type', '=', 'in'),
                ])
                created = False
                if not in_id:
                    in_id = self.pool.get('purchase.order').create_picking(cr, uid, pol.order_id, context)
                    in_id = [in_id]
                    created = True
                incoming_move_id = self.pool.get('purchase.order').create_new_incoming_line(cr, uid, in_id[0], pol, context)
                if created:
                    wf_service.trg_validate(uid, 'stock.picking', in_id[0], 'button_confirm', cr)
                else:
                    self.pool.get('stock.move').in_action_confirm(cr, uid, incoming_move_id, context)

                # create internal moves (INT):
                if pol.order_id.location_id.input_ok and pol.product_id.type not in ('service_recep', 'consu'):
                    internal_pick = self.pool.get('stock.picking').search(cr, uid, [
                        ('type', '=', 'internal'),
                        ('purchase_id', '=', pol.order_id.id),
                        ('state', 'not in', ['done', 'cancel']),
                    ], context=context)
                    created = False
                    if not internal_pick:
                        internal_pick = self.create_sys_int(cr, uid, ids, context=context)
                        internal_pick = [internal_pick]
                        created = True
                    # create and update stock.move:
                    int_move_id = self.pool.get('purchase.order').create_new_int_line(cr, uid, internal_pick[0], pol, incoming_move_id, context)
                    if created:
                        self.pool.get('stock.picking').draft_force_assign(cr, uid, internal_pick, context=context)
                    else:
                        self.pool.get('stock.move').action_confirm(cr, uid, [int_move_id], context=context)

            # if line created in PO, then create a FO line that match with it:
            if not pol.linked_sol_id and pol.origin:
                fo_id = self.update_origin_link(cr, uid, pol.origin, po_obj=pol.order_id, context=context)
                fo_id = fo_id['link_so_id'] if fo_id else False
                if fo_id:
                    new_sol_id = self.create_sol_from_pol(cr, uid, pol.id, fo_id, context=context)
                    self.write(cr, uid, pol.id, {
                        'link_so_id': fo_id,
                        'linked_sol_id': new_sol_id,
                    }, context=context)
                    wf_service.trg_validate(uid, 'sale.order.line', new_sol_id, 'confirmed', cr)

            # Confirm linked FO line:
            if pol.linked_sol_id:
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'confirmed', cr)

            self.write(cr, uid, [pol.id], {'state': 'confirmed', 'confirmation_date': datetime.now().strftime('%Y-%m-%d')}, context=context)

            if pol.order_id.order_type == 'direct':
                wf_service.trg_validate(uid, 'purchase.order.line', pol.id, 'done', cr)

            if pol.order_id.invoice_method == 'order':
                pol_to_invoice[pol.id] = True


        # create or update the linked commitment voucher:
        self.create_or_update_commitment_voucher(cr, uid, ids, context=context)
        if pol_to_invoice:
            self.generate_invoice(cr, uid, pol_to_invoice.keys(), context=context)

        return True


    def action_done(self, cr, uid, ids, context=None):
        '''
        Workflow method called when POL is done
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        # update FO line with change on PO line
        self.update_fo_lines(cr, uid, ids, context=context)

        for pol in self.browse(cr, uid, ids, context=context):
            # no PICK/OUT needed in this cases; close SO line:
            internal_ir = pol.linked_sol_id and pol.linked_sol_id.order_id.procurement_request and pol.linked_sol_id.order_id.location_requestor_id.usage == 'internal' or False  # PO line from Internal IR
            dpo = pol.order_id.order_type == 'direct' or False  # direct PO
            ir_non_stockable = pol.linked_sol_id and pol.linked_sol_id.order_id.procurement_request and pol.linked_sol_id.product_id.type in ('consu', 'service', 'service_recep') or False

            if internal_ir or dpo or ir_non_stockable:
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'done', cr)

        self.write(cr, uid, ids, {'state': 'done', 'closed_date': datetime.now().strftime('%Y-%m-%d')}, context=context)

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
        sol_obj = self.pool.get('sale.order.line')

        # cancel the linked SO line too:
        for pol in self.browse(cr, uid, ids, context=context):
            self.cancel_related_in_moves(cr, uid, pol.id, context=context)
            self.check_and_update_original_line_at_split_cancellation(cr, uid, pol.id, context=context)

            if pol.linked_sol_id:
                if pol.cancelled_by_sync:
                    sol_obj.write(cr, uid, pol.linked_sol_id.id, {'cancelled_by_sync': True}, context=context)
                wf_service.trg_validate(uid, 'sale.order.line', pol.linked_sol_id.id, 'cancel', cr)

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

        return True

    def action_cancel_r(self, cr, uid, ids, context=None):
        '''
        Wkf method called when getting the cancel_r state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        sol_obj = self.pool.get('sale.order.line')

        # cancel the linked SO line too:
        for pol in self.browse(cr, uid, ids, context=context):
            self.cancel_related_in_moves(cr, uid, pol.id, context=context)
            self.check_and_update_original_line_at_split_cancellation(cr, uid, pol.id, context=context)

            if pol.linked_sol_id and not pol.linked_sol_id.state.startswith('cancel'):
                if pol.cancelled_by_sync:
                    sol_obj.write(cr, uid, pol.linked_sol_id.id, {'cancelled_by_sync': True, 'product_uom_qty': pol.product_qty ,'product_uos_qty': pol.product_qty}, context=context)
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
        if isinstance(ids, (int, long)):
            ids = [ids]

        for po in self.browse(cr, uid, ids, context=context):
            pol_ids_to_confirm = []
            if po.partner_type == 'esc':
                pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', '=', po.id), ('state', 'in', ['validated', 'validated_p']), ('stock_take_date', '=', False)], context=context)
                if pol_ids:
                    pol_line = self.pool.get('purchase.order.line').read(cr, uid, pol_ids, ['line_number'], context=context)
                    raise osv.except_osv(_('Error'), _('Line %s: Date of Stock Take is required for PO to ESC') % ', '.join(['#%s'%x['line_number'] for x in pol_line]))

            for pol in po.order_line:
                if pol.state not in ('cancel', 'cancel_r') and not pol.confirmed_delivery_date:
                    raise osv.except_osv(_('Error'), _('Line #%s: Delivery Confirmed Date is a mandatory field.') % pol.line_number)
                pol_ids_to_confirm.append(pol.id)

            return self.pool.get('purchase.order.line').button_confirmed(cr, uid, pol_ids_to_confirm, context=context)

        return True


    def close_lines(self, cr, uid, ids, context=None):
        '''
        close all lines of the PO
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        for po in self.browse(cr, uid, ids, context=context):
            for pol in po.order_line:
                wf_service.trg_validate(uid, 'purchase.order.line', pol.id, 'done', cr)

        return True


purchase_order()
