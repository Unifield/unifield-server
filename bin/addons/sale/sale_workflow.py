# -*- coding:utf-8 -*-

from osv import osv
from tools.translate import _
import netsvc



class sale_order_line(osv.osv):
    _name = "sale.order.line"
    _inherit = "sale.order.line"


    def _get_destination_ok(self, cr, uid, lines, context):
        dest_ok = False
        for line in lines:
            dest_ok = line.account_4_distribution and line.account_4_distribution.destination_ids or False
            if not dest_ok:
                raise osv.except_osv(_('Error'), _('No destination found for this line: %s.') % (line.name or '',))
        return dest_ok


    def analytic_distribution_checks(self, cr, uid, ids, context=None):
        """
        Check analytic distribution for each sale order line (except if we come from YAML tests)
        Get a default analytic distribution if intermission.
        Change analytic distribution if intermission.
        """
        # Objects
        ana_obj = self.pool.get('analytic.distribution')
        sol_obj = self.pool.get('sale.order.line')
        distrib_line_obj = self.pool.get('cost.center.distribution.line')

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            """
            UFTP-336: Do not check AD on FO lines if the lines are
                      created on a tender or a RfQ.
                      The AD must be added on the PO line and update the
                      AD at FO line at PO confirmation.
            """
            so = line.order_id
            if line.created_by_tender or line.created_by_rfq:
                continue
            # Search intermission
            # Check distribution presence
            l_ana_dist_id = line.analytic_distribution_id and line.analytic_distribution_id.id
            o_ana_dist_id = so.analytic_distribution_id and so.analytic_distribution_id.id
            distrib_id = l_ana_dist_id or o_ana_dist_id or False

            # US-830 : Remove the definition of a default AD for the inter-mission FO is no AD is defined
            if not distrib_id and not so.order_type in ('loan', 'donation_st', 'donation_exp'):
                raise osv.except_osv(
                    _('Warning'),
                    _('Analytic distribution is mandatory for this line: %s!') % (line.name or '',),
                )

            # Check distribution state
            if distrib_id and line.analytic_distribution_state != 'valid':
                # Raise an error if no analytic distribution on line and NONE on header (because no possibility to change anything)
                if (not line.analytic_distribution_id or line.analytic_distribution_state == 'none') and \
                   not so.analytic_distribution_id:
                    # We don't raise an error for these types
                    if so.order_type not in ('loan', 'donation_st', 'donation_exp'):
                        raise osv.except_osv(
                            _('Warning'),
                            _('Analytic distribution is mandatory for this line: %s') % (line.name or '',),
                        )
                    else:
                        continue

                # Change distribution to be valid if needed by using those from header
                id_ad = ana_obj.create(cr, uid, {}, context=context)
                # Get the CC lines of the FO line if any, or the ones of the order
                cc_lines = line.analytic_distribution_id and line.analytic_distribution_id.cost_center_lines
                cc_lines = cc_lines or so.analytic_distribution_id.cost_center_lines
                for x in cc_lines:
                    # fetch compatible destinations then use one of them:
                    # - destination if compatible
                    # - else default destination of given account
                    bro_dests = self._get_destination_ok(cr, uid, [line], context=context)
                    if x.destination_id in bro_dests:
                        bro_dest_ok = x.destination_id
                    else:
                        bro_dest_ok = line.account_4_distribution.default_destination_id
                    # Copy cost center line to the new distribution
                    distrib_line_obj.copy(cr, uid, x.id, {'distribution_id': id_ad, 'destination_id': bro_dest_ok.id}, context=context)
                    # Write new distribution and link it to the line
                    sol_obj.write(cr, uid, [line.id], {'analytic_distribution_id': id_ad}, context=context)
                # UFTP-277: Check funding pool lines if missing
                ana_obj.create_funding_pool_lines(cr, uid, [id_ad], context=context)

        return True

    def copy_analytic_distribution_on_lines(self, cr, uid, ids, context=None):
        '''
        If no AD is setted on the line, then we copy the header AD on it
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # for each line get a new copy:
        for sol in self.browse(cr, uid, ids, context=context):
            for ad in [sol.analytic_distribution_id, sol.order_id.analytic_distribution_id]:
                if ad and ad.partner_type != sol.partner_id.partner_type:
                    self.pool.get('analytic.distribution').write(cr, uid, ad.id, {'partner_type': sol.partner_id.partner_type}, context=context)
                    cc_ids = [x.id for x in ad.cost_center_lines]
                    if cc_ids:
                        self.pool.get('cost.center.distribution.line').write(cr, uid, cc_ids, {'partner_type': sol.partner_id.partner_type}, context=context)

            if not sol.analytic_distribution_id and sol.order_id.analytic_distribution_id:
                self.write(cr, uid, sol.id, {
                    'analytic_distribution_id': self.pool.get('analytic.distribution').copy(cr, uid, sol.order_id.analytic_distribution_id.id, {'partner_type': sol.partner_id.partner_type}, context=context),
                })

        return True


    def check_product_or_nomenclature(self, cr, uid, ids, context=None):
        '''
        check if sale.order.line has a product_id or a nomenclature description
        If none of them are populated, then raise an error
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for sol in self.browse(cr, uid, ids, context=context):
            if not sol.product_id and sol.comment and not sol.nomenclature_description:
                raise osv.except_osv(_('Error'), _('Line %s: Please define the nomenclature levels.') % sol.line_number)

        return True

    def has_to_create_resourced_line(self, cr, uid, ids, context=None):
        '''
        in case of sol set to cancel_r, do we have to create the resourced line ?
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('sync_message_execution'):
            return False
        related_pol = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', '=', ids[0])], context=context)
        if not related_pol:
            return True
        related_pol = self.pool.get('purchase.order.line').browse(cr, uid, related_pol[0], fields_to_fetch=['original_line_id'], context=context)
        if not related_pol.original_line_id:
            return True
        return (not related_pol.original_line_id.block_resourced_line_creation)


    def create_resource_line(self, cr, uid, ids, context=None):
        '''
        create a new FO line (resourced) with given FO line (cancelled-r)
        @param ids: line to copy
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        new_sol_id = False
        for sol in self.browse(cr, uid, ids, context=context):
            if not sol.cancelled_by_sync and self.has_to_create_resourced_line(cr, uid, sol.id, context=context):
                sol_vals = {
                    'resourced_original_line': sol.id,
                    'resourced_original_remote_line': sol.sync_linked_pol or ( sol.original_line_id and sol.original_line_id.sync_linked_pol) or sol.resourced_original_remote_line or False,
                    'resourced_at_state': sol.state,
                    'is_line_split': False,
                    'analytic_distribution_id': sol.analytic_distribution_id.id or False,
                }
                new_sol_id = self.copy(cr, uid, sol.id, sol_vals, context=context)
                wf_service.trg_validate(uid, 'sale.order.line', new_sol_id, 'validated', cr)

        return new_sol_id


    def test_done(self, cr, uid, ids, context=None):
        '''
        Workflow method to test if there are OUT moves not closed for the given sale.order.line
        return true if the sol can be closed
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        sol = self.browse(cr, uid, ids[0], context=context)
        if sol.state.startswith('cancel'):
            return False

        if sol.order_id.procurement_request and (sol.order_id.location_requestor_id.usage == 'internal' or sol.product_id.type in ('consu', 'service', 'service_recep')):
            # case the sol has no OUT moves but its normal, so don't close the sol in this case:
            has_open_moves = True
        elif sol.state.startswith('cancel'):
            # if line is already cancelled, then we should not set it to closed
            has_open_moves = True
        else:
            has_open_moves = self.pool.get('stock.move').search_exist(cr, uid, [
                ('sale_line_id', '=', sol.id),
                ('state', 'not in', ['cancel', 'cancel_r', 'done']),
                ('type', '=', 'out'),
                ('product_qty', '!=', 0.0),
            ], context=context)

        return not has_open_moves


    def action_done(self, cr, uid, ids, context=None):
        '''
        Workflow method called when SO line is done
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'done'}, context=context)

        # generate sync message manually :
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        return True


    def action_sourced(self, cr, uid, ids, context=None):
        '''
        Workflow method called when sourcing the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'sourced'}, context=context)

        # generate sync message manually :
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        return True


    def action_sourced_v(self, cr, uid, ids, context=None):
        '''
        Workflow method called when sourcing the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'sourced_v'}, context=context)

        # generate sync message
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        return True


    def action_sourced_sy(self, cr, uid, ids, context=None):
        '''
        Workflow method called when the sale.order.line get the sourced_sy state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'sourced_sy'}, context=context)

        return True


    def action_sourced_n(self, cr, uid, ids, context=None):
        '''
        Workflow method called when the sale.order.line get the sourced_n state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'sourced_n'}, context=context)

        # generate sync message manually :
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        return True


    def get_existing_pick_for_dpo(self, cr, uid, ids, picking_data, context=None):
        '''
        Search for an existing PICK to use in case of SO line source on DPO
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        sol = self.browse(cr, uid, ids[0], context=context)

        pick_to_use = self.pool.get('stock.picking').search(cr, uid, [
            ('type', '=', picking_data['type']),
            ('subtype', '=', picking_data['subtype']),
            ('sale_id', '=', picking_data['sale_id']),
            ('partner_id2', '=', sol.order_partner_id.id),
            ('state', '=', 'done'),
            ('dpo_out', '=', True),
        ], context=context)

        if pick_to_use:
            # if PICK found above has already been synched, then ignore it:
            already_synched = self.pool.get('sync.client.message_to_send').search_exist(cr, 1, [
                ('identifier', 'ilike', '%%stock_picking/%s_%%' % pick_to_use[0]),
            ], context=context)
            if already_synched:
                pick_to_use = False

        return pick_to_use and pick_to_use[0] or False


    def get_existing_pick(self, cr, uid, ids, context=None):
        '''
        Search for an existing PICK/OUT/INT (depending on the flow) to use
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        pick_to_use = False

        sol = self.browse(cr, uid, ids[0], context=context)

        picking_data = self.pool.get('sale.order')._get_picking_data(cr, uid, sol.order_id, context=context, get_seq=False)

        if picking_data['subtype'] == 'standard':
            # simple OUT
            state_dom = ['draft', 'confirmed', 'assigned']
        else:
            state_dom = ['draft']

        # build domain:
        domain = [
            ('type', '=', picking_data['type']),
            ('subtype', '=', picking_data['subtype']),
            ('sale_id', '=', picking_data['sale_id']),
            ('partner_id2', '=', sol.order_partner_id.id),
            ('state', 'in', state_dom),
        ]

        # ... and search:
        pick_to_use = self.pool.get('stock.picking').search(cr, uid, domain, context=context)
        if pick_to_use:
            pick_to_use = pick_to_use[0]

        # update sequence name:
        seq_name = picking_data['seq_name']
        del(picking_data['seq_name'])

        # if no pick found, then create a new one:
        if not pick_to_use:
            picking_data['name'] = self.pool.get('ir.sequence').get(cr, uid, seq_name)
            pick_to_use = self.pool.get('stock.picking').create(cr, uid, picking_data, context=context)
            pick_name = picking_data['name']
            self.infolog(cr, uid, "The Picking Ticket id:%s (%s) has been created from %s id:%s (%s)." % (
                pick_to_use,
                pick_name,
                sol.order_id.procurement_request and _('Internal request') or _('Field order'),
                sol.order_id.id,
                sol.order_id.name,
            ))

        return pick_to_use


    def check_out_moves_to_cancel(self, cr, uid, ids, context=None):
        '''
        check if the sol to cancel are linked to OUT stock moves, if yes we must cancel them too
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        stock_move_obj = self.pool.get('stock.move')
        pick_to_check = set()


        for sol in ids:
            out_moves_to_cancel = self.pool.get('stock.move').search(cr, uid, [
                ('sale_line_id', '=', sol),
                ('type', '=', 'out'),
                ('state', 'in', ['assigned', 'confirmed']),
            ], context=context)

            if out_moves_to_cancel:
                context.update({'not_resource_move': out_moves_to_cancel})
                stock_move_obj.action_cancel(cr, uid, out_moves_to_cancel, context=context)
                context.pop('not_resource_move')
                for move in stock_move_obj.browse(cr, uid, out_moves_to_cancel, fields_to_fetch=['picking_id'], context=context):
                    pick_to_check.add(move.picking_id.id)

        # maybe the stock picking needs to be closed/cancelled :
        for pick in list(pick_to_check):
            wf_service.trg_write(uid, 'stock.picking', pick, cr)

        return True


    def action_confirmed(self, cr, uid, ids, context=None):
        '''
        Workflow method called when confirming the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        for sol in self.browse(cr, uid, ids, context=context):
            linked_dpo_line = self.pool.get('purchase.order.line').search(cr, uid, [
                ('linked_sol_id', '=', sol.id),
                ('order_id.order_type', '=', 'direct'),
            ], context=context)

            if sol.order_id.procurement_request and sol.product_id.type in ('consu', 'service', 'service_recep'):  # IR non stockable
                continue

            if linked_dpo_line:
                picking_obj = self.pool.get('stock.picking')
                # create or update PICK/OUT:
                picking_data = self.pool.get('sale.order')._get_picking_data(cr, uid, sol.order_id, context=context, get_seq=False)

                # search for an existing PICK to use:
                pick_to_use = self.get_existing_pick_for_dpo(cr, uid, sol.id, picking_data, context=context)

                # update sequence name:
                seq_name = picking_data['seq_name']
                del(picking_data['seq_name'])

                if not pick_to_use:
                    picking_data['name'] = self.pool.get('ir.sequence').get(cr, uid, seq_name)
                    pick_to_use = self.pool.get('stock.picking').create(cr, uid, picking_data, context=context)
                    pick_name = picking_data['name']
                    self.infolog(cr, uid, "The Picking Ticket id:%s (%s) has been created from %s id:%s (%s)." % (
                        pick_to_use,
                        pick_name,
                        sol.order_id.procurement_request and _('Internal request') or _('Field order'),
                        sol.order_id.id,
                        sol.order_id.name,
                    ))

                # Get move data and create the move
                move_data = self.pool.get('sale.order')._get_move_data(cr, uid, sol.order_id, sol, pick_to_use, context=context)
                move_data['dpo_line_id'] = linked_dpo_line[0]
                move_id = self.pool.get('stock.move').create(cr, uid, move_data, context=context)
                self.pool.get('stock.move').action_done(cr, uid, [move_id], context=context)
                stock_loc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
                self.pool.get('stock.move').write(cr, uid, [move_id], {'location_id': stock_loc, 'location_dest_id': stock_loc}, context=context)
                # set PICK to done
                picking_obj.action_done(cr, uid, [pick_to_use], context=context)

                # Create STV / IVO
                # Change Currency ??
                if sol.order_partner_id.partner_type in ('section', 'intermission'):
                    picking = picking_obj.browse(cr, uid, pick_to_use, context=context)
                    move = self.pool.get('stock.move').browse(cr, uid, move_id, context=context)
                    invoice_id, inv_type = picking_obj.action_invoice_create_header(cr, uid, picking, journal_id=False, invoices_group=False, type=False, use_draft=True, context=context)
                    if invoice_id:
                        picking_obj.action_invoice_create_line(cr, uid, picking, move, invoice_id, group=False, inv_type=inv_type, partner=sol.order_id.partner_id, context=context)

            else:
                picking_data = self.pool.get('sale.order')._get_picking_data(cr, uid, sol.order_id, context=context, get_seq=False)

                if sol.order_id.procurement_request and picking_data['type'] == 'internal' and sol.type != 'make_to_stock':
                    # in case of IR not sourced from stock, don't create INT
                    continue

                # create or update PICK/OUT/INT:
                pick_to_use = self.get_existing_pick(cr, uid, sol.id, context=context)

                # Get move data and create the move
                move_data = self.pool.get('sale.order')._get_move_data(cr, uid, sol.order_id, sol, pick_to_use, context=context)
                move_id = self.pool.get('stock.move').create(cr, uid, move_data, context=context)
                self.pool.get('stock.move').action_confirm(cr, uid, [move_id], context=context)

                # confirm the OUT if in draft state:
                pick_state = self.pool.get('stock.picking').read(cr, uid, pick_to_use, ['state'], context=context)['state']
                if picking_data['type'] == 'out' and picking_data['subtype'] == 'standard' and pick_state == 'draft':
                    self.pool.get('stock.picking').draft_force_assign(cr, uid, [pick_to_use], context=context)
                # run check availability on PICK/OUT:
                if picking_data['type'] == 'out' and picking_data['subtype'] in ['picking', 'standard']:
                    self.pool.get('stock.move').action_assign(cr, uid, [move_id])
                #    self.pool.get('stock.picking').action_assign(cr, uid, [pick_to_use], context=context)
                if picking_data['type'] == 'internal' and sol.type == 'make_to_stock' and sol.order_id.procurement_request:
                    wf_service.trg_validate(uid, 'stock.picking', pick_to_use, 'button_confirm', cr)

        self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

        # generate sync message:
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)
        return True

    def check_fo_tax(self, cr, uid, ids, context=None):
        """
        Prevents from validating a FO with taxes when using an Intermission or Intersection partner
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for fo_line in self.browse(cr, uid, ids, fields_to_fetch=['order_id', 'tax_id'], context=context):
            if fo_line.tax_id and fo_line.order_id.partner_type in ('intermission', 'section'):
                raise osv.except_osv(_('Error'), _("Taxes are forbidden with Intermission and Intersection partners."))

    def action_validate(self, cr, uid, ids, context=None):
        '''
        Workflow method called when validating the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        obj_data = self.pool.get('ir.model.data')

        self.check_fo_tax(cr, uid, ids, context=context)

        for sol in self.browse(cr, uid, ids, context=context):
            to_write = {}
            if sol.order_id.procurement_request and not sol.order_id.location_requestor_id:
                raise osv.except_osv(_('Warning !'),
                                     _('You can not validate the line without a Location Requestor.'))
            if not sol.order_id.procurement_request and sol.product_uom_qty*sol.price_unit >= self._max_value:
                raise osv.except_osv(_('Warning !'), _('%s line %s: %s') % (sol.order_id.name, sol.line_number, _(self._max_msg)))
            if not sol.order_id.delivery_requested_date:
                raise osv.except_osv(_('Warning !'),
                                     _('You can not validate the line without a Requested date.'))
            if not sol.product_uom \
                    or sol.product_uom.id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]:
                raise osv.except_osv(_('Error'),
                                     _('Line #%s: You cannot validate a line with no UoM.') % (sol.line_number,))
            elif not self.pool.get('uom.tools').check_uom(cr, uid, sol.product_id.id, sol.product_uom.id, context):
                raise osv.except_osv(
                    _('Error'),
                    _('Line #%s: You have to select a product UoM in the same category than the UoM of the product.')
                    % (sol.line_number,)
                )

            # US-4576: Set supplier
            if sol.type == 'make_to_order' and sol.order_id.order_type not in ['loan', 'donation_st', 'donation_exp']\
                    and sol.product_id and sol.product_id.seller_id:
                to_write['supplier'] = sol.product_id.seller_id.id

            if sol.order_id.order_type == 'loan':
                to_write['supplier'] = False
                to_write['type'] = 'make_to_stock'
                to_write['po_cft'] = False
            if not sol.original_product:
                to_write['original_product'] = sol.product_id.id
            if not sol.original_qty:
                to_write['original_qty'] = sol.product_uom_qty
            if not sol.original_price:
                to_write['original_price'] = sol.price_unit
            if not sol.original_uom:
                to_write['original_uom'] = sol.product_uom.id
            if not sol.order_id.procurement_request:  # in case of FO
                # check unit price:
                if not sol.price_unit or sol.price_unit <= 0:
                    raise osv.except_osv(
                        _('Error'),
                        _('Line #%s: You cannot validate a line with unit price as zero.') % sol.line_number
                    )
                # check analytic distribution before validating the line:
                self.analytic_distribution_checks(cr, uid, [sol.id], context=context)
                self.copy_analytic_distribution_on_lines(cr, uid, [sol.id], context=context)

                if sol.order_id.order_type in ['loan', 'donation_st', 'donation_exp'] and sol.type != 'make_to_stock':
                    to_write['type'] = 'make_to_stock'

            elif sol.order_id.procurement_request:  # in case of IR
                self.check_product_or_nomenclature(cr, uid, ids, context=context)

            if to_write:
                self.write(cr, uid, sol.id, to_write, context=context)

        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        # generate sync message:
        return_info = {}
        for sol in self.browse(cr, uid, ids, context=context):
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol.id, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        return True


    def action_draft(self, cr, uid, ids, context=None):
        '''
        Workflow method called when trying to reset draft the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'draft'}, context=context)

        return True

    def action_cancel(self, cr, uid, ids, context=None):
        '''
        Workflow method called when SO line is getting the cancel state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.check_out_moves_to_cancel(cr, uid, ids, context=context)

        initial_fo_states = dict((x.id, x.order_id.state) for x in self.browse(cr, uid, ids, fields_to_fetch=['order_id'], context=context))
        context.update({'no_check_line': True})
        vals = {'state': 'cancel'}
        so_line = self.browse(cr, uid, ids, fields_to_fetch=['order_id', 'state'], context=context)
        if so_line and (so_line[0].order_id.fo_created_by_po_sync or so_line[0].state != 'draft'):
            vals.update({'cancelled_by_sync': True})
        self.write(cr, uid, ids, vals, context=context)
        context.pop('no_check_line')

        # generate sync message:
        return_info = {}
        for sol in self.browse(cr, uid, ids, context=context):
            if not (initial_fo_states[sol.id] == 'draft' and not sol.order_id.fo_created_by_po_sync): # draft push FO
                self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol.id, return_info,
                                                                                      'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        return True

    def action_cancel_r(self, cr, uid, ids, context=None):
        '''
        Workflow method called when SO line is getting the cancel_r state
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.check_out_moves_to_cancel(cr, uid, ids, context=context)
        resourced_sol = self.create_resource_line(cr, uid, ids, context=context)

        context.update({'no_check_line': True})
        vals = {'state': 'cancel_r'}
        so_line = self.browse(cr, uid, ids, fields_to_fetch=['order_id', 'state'], context=context)
        if so_line and (so_line[0].order_id.fo_created_by_po_sync or so_line[0].state != 'draft'):
            vals.update({'cancelled_by_sync': True})
        self.write(cr, uid, ids, vals, context=context)
        context.pop('no_check_line')

        # generate sync message for original FO line:
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        # generate sync message for resourced line:
        if resourced_sol:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', resourced_sol, return_info,
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        return True


sale_order_line()



class sale_order(osv.osv):
    _name = "sale.order"
    _inherit = "sale.order"

    def validate_lines(self, cr, uid, ids, context=None):
        """
        Force SO lines validation and update SO state
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        for so in self.browse(cr, uid, ids, context=context):
            if so.procurement_request and not so.location_requestor_id:
                raise osv.except_osv(_('Warning !'),
                                     _('You can not validate \'%s\' without a Location Requestor.') % (so.name))
            if not so.delivery_requested_date:
                raise osv.except_osv(_('Warning !'),
                                     _('You can not validate \'%s\' without a Requested date.') % (so.name))
            for sol_id in [sol.id for sol in so.order_line]:
                wf_service.trg_validate(uid, 'sale.order.line', sol_id, 'validated', cr)

        return True

    def validate_ir_lines(self, cr, uid, ids, context=None):
        return self.validate_lines(cr, uid, ids, context)

    def wkf_split(self, cr, uid, ids, context=None):
        return True


sale_order()


