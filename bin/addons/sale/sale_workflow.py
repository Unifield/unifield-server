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

            #US-830 : Remove the definition of a default AD for the inter-mission FO is no AD is defined
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
        if isinstance(ids, (int,long)):
            ids = [ids]

        # for each line get a new copy:
        for sol in self.browse(cr, uid, ids, context=context):
            if not sol.analytic_distribution_id and sol.order_id.analytic_distribution_id:
                self.write(cr, uid, sol.id, {
                    'analytic_distribution_id': self.pool.get('analytic.distribution').copy(cr, uid, sol.order_id.analytic_distribution_id.id, {}, context=context),
                })

        return True


    def check_product_or_nomenclature(self, cr, uid, ids, context=None):
        '''
        check if sale.order.line has a product_id or a nomenclature description
        If none of them are populated, then raise an error
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        for sol in self.browse(cr, uid, ids, context=context):
            if not sol.product_id and sol.comment and not sol.nomenclature_description:
                raise osv.except_osv(_('Error'), _('Line %s: Please define the nomenclature levels.') % sol.line_number)

        return True


    def create_resource_line(self, cr, uid, ids, context=None):
        '''
        create a new FO line (resourced) with given FO line (cancelled-r)
        @param ids: line to copy
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        new_sol_id = False
        for sol in self.browse(cr, uid, ids, context=context):
            new_sol_id = self.copy(cr, uid, sol.id, {
                'resourced_original_line': sol.id, 
                'resourced_original_remote_line': sol.sync_linked_pol,
                'resourced_at_state': sol.state,
            }, context=context)
            wf_service.trg_validate(uid, 'sale.order.line', new_sol_id, 'validated', cr)

        return new_sol_id


    def action_done(self, cr, uid, ids, context=None):
        '''
        Workflow method called when SO line is done
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
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
        if isinstance(ids, (int,long)):
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
            already_synched = self.pool.get('sync.client.message_to_send').search_exist(cr, uid, [
                ('identifier', 'ilike', '%%stock_picking/%s_%%' % pick_to_use[0]),
            ], context=context)
            if already_synched:
                pick_to_use = False

        return pick_to_use and pick_to_use[0] or False


    def action_confirmed(self, cr, uid, ids, context=None):
        '''
        Workflow method called when confirming the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for sol in self.browse(cr, uid, ids, context=context):
            if not sol.stock_take_date and sol.order_id.stock_take_date:
                self.write(cr, uid, sol.id, {'stock_take_date': sol.order_id.stock_take_date}, context=context)

            linked_dpo_line = self.pool.get('purchase.order.line').search(cr, uid, [
                ('linked_sol_id', '=', sol.id),
                ('order_id.order_type', '=', 'direct'),
            ], context=context)
            ir_non_stockable = sol.procurement_request and sol.product_id.type in ('consu', 'service', 'service_recep')

            if linked_dpo_line:
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
                self.pool.get('stock.picking').action_done(cr, uid, [pick_to_use], context=context)

            elif not ir_non_stockable:
                # create or update PICK/OUT:
                picking_data = self.pool.get('sale.order')._get_picking_data(cr, uid, sol.order_id, context=context, get_seq=False)
                pick_to_use = self.pool.get('stock.picking').search(cr, uid, [
                    ('type', '=', picking_data['type']),
                    ('subtype', '=', picking_data['subtype']),
                    ('sale_id', '=', picking_data['sale_id']),
                    ('partner_id2', '=', sol.order_partner_id.id),
                    ('state', 'in', ['draft', 'confirmed', 'assigned']),
                ], context=context)
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
                if pick_to_use and isinstance(pick_to_use, list):
                    pick_to_use = pick_to_use[0]
                # Get move data and create the move
                move_data = self.pool.get('sale.order')._get_move_data(cr, uid, sol.order_id, sol, pick_to_use, context=context)
                move_id = self.pool.get('stock.move').create(cr, uid, move_data, context=context)
                self.pool.get('stock.move').action_confirm(cr, uid, [move_id], context=context)

                # confirm the OUT if in draft state:
                pick_state = self.pool.get('stock.picking').read(cr, uid, pick_to_use, ['state'] ,context=context)['state']
                if picking_data['type'] == 'out' and picking_data['subtype'] == 'standard' and pick_state == 'draft':
                    self.pool.get('stock.picking').draft_force_assign(cr, uid, [pick_to_use], context=context)

                # run check availability on PICK/OUT:
                if picking_data['type'] == 'out' and picking_data['subtype'] in ['picking', 'standard']:
                    self.pool.get('stock.picking').action_assign(cr, uid, [pick_to_use], context=context)

        self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

        # generate sync message:
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info, 
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)
        return True


    def action_validate(self, cr, uid, ids, context=None):
        '''
        Workflow method called when validating the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids] 

        for sol in self.browse(cr, uid, ids, context=context):
            to_write = {}
            if not sol.stock_take_date and sol.order_id.stock_take_date:
                to_write['stock_take_date'] = sol.order_id.stock_take_date
            if not sol.order_id.procurement_request: # in case of FO
                # check unit price:
                if not sol.price_unit or sol.price_unit <= 0:
                    raise osv.except_osv(
                        _('Error'),
                        _('Line #%s: You cannot validate a line with unit price as zero.' % sol.line_number)
                    )
                # check analytic distribution before validating the line:
                self.analytic_distribution_checks(cr, uid, [sol.id], context=context)
                self.copy_analytic_distribution_on_lines(cr, uid, [sol.id], context=context)

                if sol.order_id.order_type in ['loan', 'donation_st', 'donation_exp'] and sol.type != 'make_to_stock':
                    to_write['type'] = 'make_to_stock'

            elif sol.order_id.procurement_request:  # in case of IR
                to_write['original_qty'] = sol.product_uom_qty
                to_write['original_price'] = sol.price_unit
                to_write['original_uom'] = sol.product_uom.id

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


    def action_draft(self, cr ,uid, ids, context=None):
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

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

        # generate sync message:
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info, 
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

        resourced_sol = self.create_resource_line(cr, uid, ids, context=context)

        self.write(cr, uid, ids, {'state': 'cancel_r'}, context=context)

        # generate sync message for original FO line:
        return_info = {}
        for sol_id in ids:
            self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', sol_id, return_info, 
                                                                                  'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context)

        # generate sync message for resourced line:
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
            for sol_id in [sol.id for sol in so.order_line]:
                wf_service.trg_validate(uid, 'sale.order.line', sol_id, 'validated', cr)

        return True

    def wkf_split(self, cr, uid, ids, context=None):
        return True


sale_order()


