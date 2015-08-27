#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest

import time

class PickConvertToStandardTest(ResourcingTest):

    def setUp(self):
        """
        Create a PO at Project side to Coordo with
        two lines.
        :return:
        """
        super(PickConvertToStandardTest, self).setUp()

        self.c_in_ids = []
        self.c_out_ids = []

        # C1
        self.c_so_obj = self.c1.get('sale.order')
        self.c_sol_obj = self.c1.get('sale.order.line')
        self.c_po_obj = self.c1.get('purchase.order')
        self.c_pol_obj = self.c1.get('purchase.order.line')
        self.c_partner_obj = self.c1.get('res.partner')
        self.c_lc_obj = self.c1.get('sale.order.leave.close')
        self.c_so_cancel_obj = self.c1.get('sale.order.cancelation.wizard')
        self.c_pick_obj = self.c1.get('stock.picking')
        self.c_move_obj = self.c1.get('stock.move')
        self.c_ship_obj = self.c1.get('shipment')
        self.c_enter_reason_obj = self.c1.get('enter.reason')
        self.c_proc_in_obj = self.c1.get('stock.incoming.processor')
        self.c_move_in_obj = self.c1.get('stock.move.in.processor')

        # Prepare values for the field order
        prod_log1_id = self.get_record(self.c1, 'prod_log_1')
        prod_log2_id = self.get_record(self.c1, 'prod_log_2')
        uom_pce_id = self.get_record(self.c1, 'product_uom_unit', module='product')
        ext_cu = self.get_record(self.c1, 'external_cu')

        partner_name = self.get_db_partner_name(self.p1)
        partner_ids = self.c_partner_obj.search([('name', '=', partner_name)])
        if not partner_ids:
            self.synchronize(self.c1)
            partner_ids = self.c_partner_obj.search([('name', '=', partner_name)])
        self.assert_(
            partner_ids,
            "No partner found for %s" % self.p1.db_name,
        )

        distrib_id = self.create_analytic_distribution(self.c1)

        order_values = {
            'order_type': 'regular',
            'partner_id': partner_ids[0],
            'analytic_distribution_id': distrib_id,
        }

        change_vals = self.c_so_obj.\
            onchange_partner_id(None, partner_ids[0], 'regular').get('value', {})
        order_values.update(change_vals)

        order_values['ready_to_ship_date'] = time.strftime('%Y-%m-%d')

        self.c_so_id = self.c_so_obj.create(order_values)

        # Create order lines
        # First line
        line_values = {
            'order_id': self.c_so_id,
            'product_id': prod_log1_id,
            'product_uom': uom_pce_id,
            'product_uom_qty': 10.0,
            'type': 'make_to_order',
            'price_unit': 300.99
        }
        self.c_sol_obj.create(line_values)

        # Second line
        line_values.update({
            'product_id': prod_log2_id,
            'product_uom_qty': 20.0,
        })
        self.c_sol_obj.create(line_values)

        # Validate the sale order
        self.c1.exec_workflow('sale.order', 'order_validated', self.c_so_id)

        # Source all lines on a Purchase Order to ext_supplier_1
        line_ids = self.c_sol_obj.search([('order_id', '=', self.c_so_id)])
        self.c_sol_obj.write(line_ids, {
            'po_cft': 'po',
            'supplier': self.get_record(self.c1, 'ext_supplier_1'),
        })
        self.c_sol_obj.confirmLine(line_ids)

        # Run the scheduler
        self.c_so_id = self.run_auto_pos_creation(self.c1, order_to_check=self.c_so_id)

        line_ids = self.c_sol_obj.search([('order_id', '=', self.c_so_id)])
        not_sourced = True
        while not_sourced:
            not_sourced = False
            for line in self.c_sol_obj.browse(line_ids):
               if line.procurement_id and line.procurement_id.state != 'running':
                    not_sourced = True
            if not_sourced:
                time.sleep(1)

        po_ids = set()
        po_line_ids = []
        for line in self.c_sol_obj.browse(line_ids):
            if line.procurement_id:
                po_line_ids.extend(self.c_pol_obj.search([
                    ('procurement_id', '=', line.procurement_id.id),
                ]))

        for po_line in self.c_pol_obj.read(po_line_ids, ['order_id']):
            po_ids.add(po_line['order_id'][0])

        self.c_po_id = po_ids and list(po_ids)[0] or False
        self.c_so_name = self.c_so_obj.read(self.c_so_id, ['name'])['name']

        # Validate and confirm the PO
        self._validate_po(self.c1, [self.c_po_id])
        self._confirm_po(self.c1, [self.c_po_id])

        # Get the IN associated to this PO
        self.c_in_ids = self.c_pick_obj.search([('purchase_id', '=', self.c_po_id), ('type', '=', 'in')])
        self.c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out')])

    def tearDown(self):
        return

    def process_incoming(self):
        proc_res = self.c_pick_obj.action_process(self.c_in_ids)
        proc_id = proc_res.get('res_id')
        self.c_proc_in_obj.copy_all([proc_id])
        self.c_proc_in_obj.do_incoming_shipment([proc_id])
        self.c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out')])

    def process_out(self, out_ids):
        proc_out_obj = self.c1.get('outgoing.delivery.processor')
        proc_out_move_obj = self.c1.get('outgoing.delivery.move.processor')

        if isinstance(out_ids, (int, long)):
            out_ids = [out_ids]

        for out_id in out_ids:
            proc_res = self.c_pick_obj.action_process([out_id])
            proc_out_obj.copy_all([proc_res.get('res_id')])
            proc_out_obj.do_partial([proc_res.get('res_id')])

    def create_pick(self, pick_ids, full=False):
        proc_obj = self.c1.get('create.picking.processor')
        proc_move_obj = self.c1.get('create.picking.move.processor')

        if isinstance(pick_ids, (int, long)):
            pick_ids = [pick_ids]

        for pick_id in pick_ids:
            proc_res = self.c_pick_obj.create_picking([pick_id])
            if full:
                proc_obj.copy_all([proc_res.get('res_id')])
            else:
                proc_move_ids = proc_move_obj.search([('wizard_id', '=', proc_res.get('res_id'))])
                proc_move_qty = proc_move_obj.browse(proc_move_ids[0]).ordered_quantity
                proc_move_obj.write([proc_move_ids[0]], {'quantity': proc_move_qty})
            proc_obj.do_create_picking([proc_res.get('res_id')])

        self.c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out')])

    def validate_pick(self, pick_ids, full=False):
        proc_obj = self.c1.get('validate.picking.processor')
        proc_move_obj = self.c1.get('validate.move.processor')

        if isinstance(pick_ids, (int, long)):
            pick_ids = [pick_ids]

        for pick_id in pick_ids:
            proc_res = self.c_pick_obj.validate_picking([pick_id])
            if full:
                proc_obj.copy_all([proc_res.get('res_id')])
            else:
                proc_move_ids = proc_move_obj.search([('wizard_id', '=', proc_res.get('res_id'))])
                proc_move_qty = proc_move_obj.browse(proc_move_ids[0]).ordered_quantity
                proc_move_obj.write([proc_move_ids[0]], {'quantity': proc_move_qty})
            proc_obj.do_validate_picking([proc_res.get('res_id')])

    def do_ppl(self, ppl_ids):
        proc_obj = self.c1.get('ppl.processor')
        proc_move_obj = self.c1.get('ppl.move.processor')
        proc_fam_obj = self.c1.get('ppl.family.processor')

        if isinstance(ppl_ids, (int, long)):
            ppl_ids = [ppl_ids]

        ship_id = False
        for ppl_id in ppl_ids:
            proc_res = self.c_pick_obj.ppl([ppl_id])
            proc_res2 = proc_obj.do_ppl_step1([proc_res.get('res_id')])
            fam_ids = proc_fam_obj.search([('wizard_id', '=', proc_res2.get('res_id'))])
            proc_fam_obj.write(fam_ids, {'weight': 1.00})
            ship_id = proc_obj.do_ppl_step2([proc_res2.get('res_id')]).get('res_id')

        return ship_id

    def create_shipment(self, ship_ids):
        proc_obj = self.c1.get('shipment.processor')

        if isinstance(ship_ids, (int, long)):
            ship_ids = [ship_ids]

        v_ship_id = False
        for ship_id in ship_ids:
            proc_res = self.c_ship_obj.create_shipment([ship_id])
            v_ship_id = proc_obj.do_create_shipment([proc_res.get('res_id')]).get('res_id')

        return v_ship_id

    def test_fake(self):
        return

    def check_draft_pick_move_state(self, draft_picks):
        return

    def test_0001_convert_draft_pick(self):
        """
        Before the processing of the reception, convert to standard the draft picking ticket
        """
        conv_res = self.c_pick_obj.convert_to_standard(self.c_out_ids)
        c_pick_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'picking')])
        c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'standard')])

        # Check tehre is no Draft PT and one OUT
        self.assert_(
            len(c_pick_ids) == 0,
            "After converting a draft picking ticket, there is also a draft picking ticket in DB")
        self.assert_(
            len(c_out_ids) == 1,
            "After converting a draft picking ticket, there is not Outgoing delivery in DB")

        self.process_incoming()
        self.process_out(c_out_ids)

    def test_0002_convert_full_validated_pick(self):
        """
        Process the reception, then convert to standard the validated picking ticket
        """
        self.process_incoming()

        draft_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'draft'), ('subtype', '=', 'picking')])
        valid_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'assigned'), ('subtype', '=', 'picking')])

        conv_res = self.c_pick_obj.convert_to_standard(valid_pick_ids)
        domain = [('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'picking')]
        valid_picks = self.c_pick_obj.search(domain + [('state', '=', 'assigned')])
        draft_picks = self.c_pick_obj.search(domain + [('state', '=', 'draft')])
        closed_picks = self.c_pick_obj.search(domain + [('state', '=', 'done')])
        out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'standard')])

        # Check there is no Validated PT, draft PT is now closed, and there is one OUT
        self.assert_(
            len(valid_picks) == 0,
            "After converting a validated picking ticket, there is also a validated picking ticket in DB")
        self.assert_(
            len(draft_picks) == 0,
            "After converting a validated picking ticket, the draft picking ticket is always in draft")
        self.assert_(
            len(closed_picks) == 1,
            "After converting a validated picking ticket, the draft picking ticket was not closed")
        self.assert_(
            len(out_ids) == 1,
            "After converting a validated picking ticket, there is no Outgoing delivery in DB")

        self.process_out(out_ids)

    def test_0003_convert_partial_validated_pick(self):
        """
        Before processing of the reception, create a validated picking ticket
        with partial quantities, then convert to standard this validated picking ticket
        """
        # Force the availability on the Draft picking ticket
        self.c_pick_obj.force_assign(self.c_out_ids)

        # Create a partial validated picking ticket
        self.create_pick(self.c_out_ids)

        valid_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'assigned'), ('subtype', '=', 'picking')])
        conv_res = self.c_pick_obj.convert_to_standard(valid_pick_ids)
        domain = [('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'picking')]
        valid_picks = self.c_pick_obj.search(domain + [('state', '=', 'assigned')])
        draft_picks = self.c_pick_obj.search(domain + [('state', '=', 'draft')])
        closed_picks = self.c_pick_obj.search(domain + [('state', '=', 'done')])
        out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'standard')])

        # Check there is no Validated PT, draft PT is now closed, and there is one OUT
        self.assert_(
            len(valid_picks) == 0,
            "After converting a validated picking ticket, there is also a validated picking ticket in DB")
        self.assert_(
            len(draft_picks) == 1,
            "After converting a validated picking ticket, the draft picking ticket is not in draft")
        self.assert_(
            len(closed_picks) == 0,
            "After converting a validated picking ticket, the draft picking ticket is closed")
        self.assert_(
            len(out_ids) == 1,
            "After converting a validated picking ticket, there is no Outgoing delivery in DB")
        self.check_draft_pick_move_state(draft_picks)
        self.process_incoming()

        self.process_out(out_ids)

        return draft_picks

    def test_0004_convert_partial_ppl(self):
        """
        Process the reception, then validate partially the validated picking ticket
        then convert to standard the draft picking ticket
        """
        self.process_incoming()
        valid_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'assigned'), ('subtype', '=', 'picking')])
        draft_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'draft'), ('subtype', '=', 'picking')])
        self.validate_pick(valid_pick_ids)

        conv_res = self.c_pick_obj.convert_to_standard(draft_pick_ids)
        domain = [('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'picking')]
        valid_picks = self.c_pick_obj.search(domain + [('state', '=', 'assigned')])
        draft_picks = self.c_pick_obj.search(domain + [('state', '=', 'draft')])
        closed_picks = self.c_pick_obj.search(domain + [('state', '=', 'done')])
        out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'standard')])

        # Check there is no Validated PT, draft PT is now closed, and there is one OUT
        self.assert_(
            len(valid_picks) == 0,
            "After converting a draft picking ticket, there is also a validated picking ticket in DB")
        self.assert_(
            len(draft_picks) == 1,
            "After converting a draft picking ticket, the draft picking ticket is not in draft")
        self.assert_(
            len(closed_picks) == 1,
            "After converting a draft picking ticket, the draft picking ticket was not closed")
        self.assert_(
            len(out_ids) == 1,
            "After converting a draft picking ticket, there is no Outgoing delivery in DB")
        self.check_draft_pick_move_state(draft_picks)

        self.process_out(out_ids)

        return draft_picks

    def test_0005_convert_partial_shipment(self):
        """
        Process the reception, then validate partially the validated picking ticket,
        make the packing, then convert to standard the draft picking ticket
        """
        self.process_incoming()

        valid_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'assigned'), ('subtype', '=', 'picking')])
        draft_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'draft'), ('subtype', '=', 'picking')])
        self.validate_pick(valid_pick_ids)

        ppl_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'ppl')])
        ship_id = self.do_ppl(ppl_ids)

        conv_res = self.c_pick_obj.convert_to_standard(draft_pick_ids)
        domain = [('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'picking')]
        valid_picks = self.c_pick_obj.search(domain + [('state', '=', 'assigned')])
        draft_picks = self.c_pick_obj.search(domain + [('state', '=', 'draft')])
        closed_picks = self.c_pick_obj.search(domain + [('state', '=', 'done')])
        out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'standard')])

        # Check there is no Validated PT, draft PT is now closed, and there is one OUT
        self.assert_(
            len(valid_picks) == 0,
            "After converting a draft picking ticket, there is also a validated picking ticket in DB")
        self.assert_(
            len(draft_picks) == 1,
            "After converting a draft picking ticket, the draft picking ticket is not in draft")
        self.assert_(
            len(closed_picks) == 1,
            "After converting a draft picking ticket, the draft picking ticket was not closed")
        self.assert_(
            len(out_ids) == 1,
            "After converting a draft picking ticket, there is no Outgoing delivery in DB")
        self.check_draft_pick_move_state(draft_picks)

        if ship_id:
            v_ship_id = self.create_shipment(ship_id)
            if v_ship_id:
                self.c1.get('shipment').validate([v_ship_id])

        self.process_out(out_ids)

        return draft_picks

    def test_0006_convert_partial_validated_shipment(self):
        """
        Process the reception, then validate partially the validated picking ticket,
        make the packing, validate the shipment, then convert to standard the
        draft picking ticket
        """
        self.process_incoming()

        valid_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'assigned'), ('subtype', '=', 'picking')])
        draft_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'draft'), ('subtype', '=', 'picking')])
        self.validate_pick(valid_pick_ids)

        ppl_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'ppl')])
        ship_id = self.do_ppl(ppl_ids)

        v_ship_id = False
        if ship_id:
            v_ship_id = self.create_shipment(ship_id)

        conv_res = self.c_pick_obj.convert_to_standard(draft_pick_ids)
        domain = [('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'picking')]
        valid_picks = self.c_pick_obj.search(domain + [('state', '=', 'assigned')])
        draft_picks = self.c_pick_obj.search(domain + [('state', '=', 'draft')])
        closed_picks = self.c_pick_obj.search(domain + [('state', '=', 'done')])
        out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'standard')])

        # Check there is no Validated PT, draft PT is now closed, and there is one OUT
        self.assert_(
            len(valid_picks) == 0,
            "After converting a draft picking ticket, there is also a validated picking ticket in DB")
        self.assert_(
            len(draft_picks) == 1,
            "After converting a draft picking ticket, the draft picking ticket is not in draft")
        self.assert_(
            len(closed_picks) == 1,
            "After converting a draft picking ticket, the draft picking ticket was not closed")
        self.assert_(
            len(out_ids) == 1,
            "After converting a draft picking ticket, there is no Outgoing delivery in DB")
        self.check_draft_pick_move_state(draft_picks)

        if v_ship_id:
            self.c1.get('shipment').validate([v_ship_id])

        self.process_out(out_ids)

        return draft_picks

    def test_0007_convert_partial_closed_shipment(self):
        """
        Process the reception, the validated partially the validated picking ticket,
        make the packing, validate the shipment, close the shipment, then convert
        to standard the draft picking ticket
        """
        self.process_incoming()

        valid_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'assigned'), ('subtype', '=', 'picking')])
        draft_pick_ids = self.c_pick_obj.search([('id', 'in', self.c_out_ids), ('state', '=', 'draft'), ('subtype', '=', 'picking')])
        self.validate_pick(valid_pick_ids)

        ppl_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'ppl')])
        ship_id = self.do_ppl(ppl_ids)

        if ship_id:
            v_ship_id = self.create_shipment(ship_id)
            if v_ship_id:
                self.c1.get('shipment').validate([v_ship_id])

        conv_res = self.c_pick_obj.convert_to_standard(draft_pick_ids)
        domain = [('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'picking')]
        valid_picks = self.c_pick_obj.search(domain + [('state', '=', 'assigned')])
        draft_picks = self.c_pick_obj.search(domain + [('state', '=', 'draft')])
        closed_picks = self.c_pick_obj.search(domain + [('state', '=', 'done')])
        out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out'), ('subtype', '=', 'standard')])

        # Check there is no Validated PT, draft PT is now closed, and there is one OUT
        self.assert_(
            len(valid_picks) == 0,
            "After converting a draft picking ticket, there is also a validated picking ticket in DB")
        self.assert_(
            len(draft_picks) == 0,
            "After converting a draft picking ticket, the draft picking ticket is always in draft")
        self.assert_(
            len(closed_picks) == 1,
            "After converting a draft picking ticket, the draft picking ticket was not closed")
        self.assert_(
            len(out_ids) == 1,
            "After converting a draft picking ticket, there is no Outgoing delivery in DB")

        self.process_out(out_ids)

class PickConvertToStandardPartialTest(PickConvertToStandardTest):

    def create_pick(self, pick_ids, full=False):
        proc_obj = self.c1.get('create.picking.processor')
        proc_move_obj = self.c1.get('create.picking.move.processor')

        if isinstance(pick_ids, (int, long)):
            pick_ids = [pick_ids]

        for pick_id in pick_ids:
            proc_res = self.c_pick_obj.create_picking([pick_id])
            if full:
                proc_obj.copy_all([proc_res.get('res_id')])
            else:
                proc_move_ids = proc_move_obj.search([('wizard_id', '=', proc_res.get('res_id'))])
                for proc_move_id in proc_move_ids:
                    proc_move_qty = proc_move_obj.browse(proc_move_id).ordered_quantity
                    proc_move_obj.write([proc_move_id], {'quantity': proc_move_qty-1})
            proc_obj.do_create_picking([proc_res.get('res_id')])

        self.c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out')])

    def validate_pick(self, pick_ids, full=False):
        proc_obj = self.c1.get('validate.picking.processor')
        proc_move_obj = self.c1.get('validate.move.processor')

        if isinstance(pick_ids, (int, long)):
            pick_ids = [pick_ids]

        for pick_id in pick_ids:
            proc_res = self.c_pick_obj.validate_picking([pick_id])
            if full:
                proc_obj.copy_all([proc_res.get('res_id')])
            else:
                proc_move_ids = proc_move_obj.search([('wizard_id', '=', proc_res.get('res_id'))])
                for proc_move_id in proc_move_ids:
                    proc_move_qty = proc_move_obj.browse(proc_move_id).ordered_quantity
                    proc_move_obj.write([proc_move_id], {'quantity': proc_move_qty-1})
            proc_obj.do_validate_picking([proc_res.get('res_id')])

    def check_draft_pick_move_state(self, draft_picks):
        move_ids = self.c_move_obj.search([('picking_id', 'in', draft_picks)])
        moves = self.c_move_obj.read(move_ids, ['state'])
        self.assert_(
            all(x['state'] == 'assigned' for x in moves),
            "All moves in the draft picking ticket are not draft and should be")

def get_test_suite():
    return PickConvertToStandardTest, PickConvertToStandardTest
