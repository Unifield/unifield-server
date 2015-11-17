#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest

import time


class SyncCancelINTest(ResourcingTest):

    def setUp(self):
        """
        Create a PO at Project side to Coordo with
        two lines.
        :return:
        """
        super(SyncCancelINTest, self).setUp()

        if not hasattr(self, 'procurement_request'):
            self.procurement_request = False

        self.synchronize(self.c1)
        self.synchronize(self.p1)

        # C1
        self.c_so_obj = self.c1.get('sale.order')
        self.c_sol_obj = self.c1.get('sale.order.line')
        self.c_po_obj = self.c1.get('purchase.order')
        self.c_pol_obj = self.c1.get('purchase.order.line')
        self.c_partner_obj = self.c1.get('res.partner')
        self.c_lc_obj = self.c1.get('sale.order.leave.close')
        self.c_so_cancel_obj = self.c1.get('sale.order.cancelation.wizard')
        self.c_pick_obj = self.c1.get('stock.picking')
        self.c_enter_reason_obj = self.c1.get('enter.reason')
        self.c_proc_in_obj = self.c1.get('stock.incoming.processor')
        self.c_move_in_obj = self.c1.get('stock.move.in.processor')
        self.c_proc_out_obj = self.c1.get('outgoing.delivery.processor')
        self.c_proc_out_move_obj = self.c1.get('outgoing.delivery.move.processor')

        # P1
        self.p_so_obj = self.p1.get('sale.order')
        self.p_sol_obj = self.p1.get('sale.order.line')
        self.p_po_obj = self.p1.get('purchase.order')
        self.p_pol_obj = self.p1.get('purchase.order.line')
        self.p_partner_obj = self.p1.get('res.partner')
        self.p_pick_obj = self.p1.get('stock.picking')
        self.p_move_obj = self.p1.get('stock.move')

        # Prepare values for the field order
        prod_log1_id = self.get_record(self.c1, 'prod_log_1')
        prod_log2_id = self.get_record(self.c1, 'prod_log_2')
        uom_pce_id = self.get_record(self.c1, 'product_uom_unit', module='product')
        ext_cu = self.get_record(self.c1, 'external_cu')

        partner_name = self.get_db_partner_name(self.p1)
        partner_ids = self.c_partner_obj.search([('name', '=', partner_name)])
        self.assert_(
            partner_ids,
            "No partner found for %s" % self.p1.db_name,
        )

        distrib_id = self.create_analytic_distribution(self.c1)

        order_values = {
            'order_type': 'regular',
            'partner_id': partner_ids[0],
            'procurement_request': self.procurement_request,
            'analytic_distribution_id': distrib_id,
            'location_requestor_id': self.procurement_request and ext_cu or False,
        }

        change_vals = self.c_so_obj.\
            onchange_partner_id(None, partner_ids[0], 'regular').get('value', {})
        order_values.update(change_vals)

        order_values['ready_to_ship_date'] = time.strftime('%Y-%m-%d')
        if self.procurement_request:
            order_values['delivery_requested_date'] = time.strftime('%Y-%m-%d')

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
        if self.procurement_request:
            self.c1.exec_workflow('sale.order', 'procurement_validate', self.c_so_id)
        else:
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

    def launch_sync(self):
        self.synchronize(self.c1)
        self.synchronize(self.p1)
        self.synchronize(self.c1)

    def process_partial_and_cancel_in(self):
        # Process partially the IN
        proc_res = self.c_pick_obj.action_process(self.c_in_ids)
        proc_id = proc_res.get('res_id')
        move_in_ids = self.c_move_in_obj.search([('wizard_id', '=', proc_id)])
        for move_in in self.c_move_in_obj.browse(move_in_ids):
            self.c_move_in_obj.write([move_in.id], {'quantity': 2})
        self.c_proc_in_obj.do_incoming_shipment([proc_id])

        # Cancel the IN
        wiz_id = self.c_enter_reason_obj.create({
            'picking_id': self.c_in_ids[0],
            'change_reason': 'test_cancel_in_at_coordo',
        })
        ctx = {
            'active_ids': self.c_in_ids,
        }
        self.c_enter_reason_obj.do_cancel([wiz_id], ctx)

    def test_sync_then_cancel(self):
        self.launch_sync()
        self.process_partial_and_cancel_in()

        self.c_out_ids = self.c_pick_obj.search([
            ('sale_id', '=', self.c_so_id),
            ('type', '=', 'out'),
            ('state', '!=', 'draft')
        ])
        conv_res = self.c_pick_obj.convert_to_standard(self.c_out_ids)
        out_id = conv_res.get('res_id')
        proc_res = self.c_pick_obj.action_process([out_id])
        self.c_proc_out_obj.copy_all([proc_res.get('res_id')])
        self.c_proc_out_obj.do_partial([proc_res.get('res_id')])

        self.launch_sync()

        p_po_ids = self.p_po_obj.search([('partner_ref', 'like', self.c_so_name)])
        p_in_ids = self.p_pick_obj.search([('purchase_id', 'in', p_po_ids)])
        p_move_ids = self.p_move_obj.search([('picking_id', 'in', p_in_ids)])
        res = {'cancel': 0, 'assigned': 0}
        pick_res = {'done': 0, 'shipped': 0}
        for p_move in self.p_move_obj.browse(p_move_ids):
            res.setdefault(p_move.state, 0)
            res[p_move.state] += 1
            pick_res.setdefault(p_move.picking_id.state, 0)
            pick_res[p_move.picking_id.state] += 1

        self.assert_(
            pick_res['done'] == 2 and pick_res['shipped'] == 2,
            "The number of IN by states is not correct :: Should be {'done': 2, 'shipped': 2} :: It is %s" % pick_res,
        )
        self.assert_(
            res['cancel'] == 2 and res['assigned'] == 2,
            "The number of IN moves by states is not correct :: Should be {'cancel': 2, 'assigned': 2} :: It is %s" % res,
        )

    def test_cancel_sync_before_out_processing(self):
        self.process_partial_and_cancel_in()

        self.launch_sync()

        self.c_out_ids = self.c_pick_obj.search([
            ('sale_id', '=', self.c_so_id),
            ('type', '=', 'out'),
            ('state', '!=', 'draft')
        ])
        conv_res = self.c_pick_obj.convert_to_standard(self.c_out_ids)
        out_id = conv_res.get('res_id')
        proc_res = self.c_pick_obj.action_process([out_id])
        self.c_proc_out_obj.copy_all([proc_res.get('res_id')])
        self.c_proc_out_obj.do_partial([proc_res.get('res_id')])

        self.launch_sync()

        p_po_ids = self.p_po_obj.search([('partner_ref', 'like', self.c_so_name)])
        p_in_ids = self.p_pick_obj.search([('purchase_id', 'in', p_po_ids)])
        p_move_ids = self.p_move_obj.search([('picking_id', 'in', p_in_ids)])
        res = {'cancel': 0, 'assigned': 0}
        pick_res = {'done': 0, 'shipped': 0}
        for p_move in self.p_move_obj.browse(p_move_ids):
            res.setdefault(p_move.state, 0)
            res[p_move.state] += 1
            pick_res.setdefault(p_move.picking_id.state, 0)
            pick_res[p_move.picking_id.state] += 1

        self.assert_(
            pick_res['done'] == 2 and pick_res['shipped'] == 2,
            "The number of IN by states is not correct :: Should be {'done': 0, 'shipped': 2} :: It is %s" % pick_res,
        )
        self.assert_(
            res['cancel'] == 2 and res['assigned'] == 2,
            "The number of IN moves by states is not correct :: Should be {'cancel': 0, 'assigned': 2} :: It is %s" % res,
        )

    def test_cancel_sync_partial_out_processing(self):
        self.launch_sync()

        self.process_partial_and_cancel_in()

        self.c_out_ids = self.c_pick_obj.search([
            ('sale_id', '=', self.c_so_id),
            ('type', '=', 'out'),
            ('state', '!=', 'draft')
        ])
        conv_res = self.c_pick_obj.convert_to_standard(self.c_out_ids)
        out_id = conv_res.get('res_id')
        proc_res = self.c_pick_obj.action_process([out_id])
        out_move_ids = self.c_proc_out_move_obj.search([
            ('wizard_id', '=', proc_res.get('res_id')),
        ])
        for out_move in self.c_proc_out_move_obj.browse(out_move_ids):
            self.c_proc_out_move_obj.write(out_move.id, {'quantity': 1})
        self.c_proc_out_obj.do_partial([proc_res.get('res_id')])

        self.launch_sync()

        p_po_ids = self.p_po_obj.search([('partner_ref', 'like', self.c_so_name)])
        p_in_ids = self.p_pick_obj.search([('purchase_id', 'in', p_po_ids)])
        p_move_ids = self.p_move_obj.search([('picking_id', 'in', p_in_ids)])
        res = {'cancel': 0, 'assigned': 0}
        pick_res = {'done': 0, 'shipped': 0, 'assigned': 0}
        for p_move in self.p_move_obj.browse(p_move_ids):
            res.setdefault(p_move.state, 0)
            res[p_move.state] += 1
            pick_res.setdefault(p_move.picking_id.state, 0)
            pick_res[p_move.picking_id.state] += 1

        self.assert_(
            pick_res['assigned'] == 2 and pick_res['shipped'] == 2,
            "The number of IN by states is not correct :: Should be {'assigned': 2, 'shipped': 2} :: It is %s" % pick_res,
        )
        self.assert_(
            res['assigned'] == 4,
            "The number of IN moves by states is not correct :: Should be {'assigned': 2} :: It is %s" % res,
        )

        proc_res = self.c_pick_obj.action_process([out_id])
        self.c_proc_out_obj.copy_all([proc_res.get('res_id')])
        self.c_proc_out_obj.do_partial([proc_res.get('res_id')])

        self.launch_sync()

        p_po_ids = self.p_po_obj.search([('partner_ref', 'like', self.c_so_name)])
        p_in_ids = self.p_pick_obj.search([('purchase_id', 'in', p_po_ids)])
        p_move_ids = self.p_move_obj.search([('picking_id', 'in', p_in_ids)])
        res = {'cancel': 0, 'assigned': 0}
        pick_res = {'done': 0, 'shipped': 0, 'assigned': 0}
        for p_move in self.p_move_obj.browse(p_move_ids):
            res.setdefault(p_move.state, 0)
            res[p_move.state] += 1
            pick_res.setdefault(p_move.picking_id.state, 0)
            pick_res[p_move.picking_id.state] += 1

        self.assert_(
            pick_res['done'] == 2 and pick_res['shipped'] == 4,
            "The number of IN by states is not correct :: Should be {'done': 2, 'shipped': 4} :: It is %s" % pick_res,
        )
        self.assert_(
            res['cancel'] == 2 and res['assigned'] == 4,
            "The number of IN moves by states is not correct :: Should be {'assigned': 4, 'cancel': 2} :: It is %s" % res,
        )


    def test_cancel_then_sync(self):
        self.process_partial_and_cancel_in()

        self.c_out_ids = self.c_pick_obj.search([
            ('sale_id', '=', self.c_so_id),
            ('type', '=', 'out'),
            ('state', '!=', 'draft')
        ])
        conv_res = self.c_pick_obj.convert_to_standard(self.c_out_ids)
        out_id = conv_res.get('res_id')
        proc_res = self.c_pick_obj.action_process([out_id])
        self.c_proc_out_obj.copy_all([proc_res.get('res_id')])
        self.c_proc_out_obj.do_partial([proc_res.get('res_id')])

        self.launch_sync()

        p_po_ids = self.p_po_obj.search([('partner_ref', 'like', self.c_so_name)])
        p_in_ids = self.p_pick_obj.search([('purchase_id', 'in', p_po_ids)])
        p_move_ids = self.p_move_obj.search([('picking_id', 'in', p_in_ids)])
        res = {'cancel': 0, 'assigned': 0}
        pick_res = {'done': 0, 'shipped': 0}
        for p_move in self.p_move_obj.browse(p_move_ids):
            res.setdefault(p_move.state, 0)
            res[p_move.state] += 1
            pick_res.setdefault(p_move.picking_id.state, 0)
            pick_res[p_move.picking_id.state] += 1

        self.assert_(
            pick_res['done'] == 2 and pick_res['shipped'] == 2,
            "The number of IN by states is not correct :: Should be {'done': 0, 'shipped': 2} :: It is %s" % pick_res,
        )
        self.assert_(
            res['cancel'] == 2 and res['assigned'] == 2,
            "The number of IN moves by states is not correct :: Should be {'cancel': 0, 'assigned': 2} :: It is %s" % res,
        )

def get_test_class():
    return SyncCancelINTest
