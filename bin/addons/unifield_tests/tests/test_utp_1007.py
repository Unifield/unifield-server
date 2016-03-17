#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest

import time


class UTP1007Test(ResourcingTest):

    def setUp(self):
        """
        Set the test as an IR test

        1/ Create an IR with one line of 100 PCE
        2/ Source the IR to external partner
        3/ Validate and confirm the PO
        4/ Receive 98 PCE
        5/ Cancel and resource the backorder
        """
        super(UTP1007Test, self).setUp()
        self.c_so_obj = self.c1.get('sale.order')
        self.c_sol_obj = self.c1.get('sale.order.line')
        self.c_po_obj = self.c1.get('purchase.order')
        self.c_pol_obj = self.c1.get('purchase.order.line')
        self.c_proc_obj = self.c1.get('stock.incoming.processor')
        self.c_proc_line_obj = self.c1.get('stock.move.in.processor')
        self.c_pick_obj = self.c1.get('stock.picking')
        self.c_enter_reason_obj = self.c1.get('enter.reason')

        # Prepare values for the internal request
        prod_log1_id = self.get_record(self.c1, 'prod_log_1')
        uom_pce_id = self.get_record(self.c1, 'product_uom_unit', module='product')
        distrib_id = self.create_analytic_distribution(self.c1)

        """
        1/ Create an IR with one line of 10

        """
        order_values = {
            'procurement_request': True,
            'location_requestor_id': self.get_record(self.c1, 'stock_location_stock', module='stock'),
        }

        self.c_so_id = self.c_so_obj.create(order_values)

        # Create order lines
        # First line
        line_values = {
            'order_id': self.c_so_id,
            'product_id': prod_log1_id,
            'product_uom': uom_pce_id,
            'product_uom_qty': 100.0,
            'type': 'make_to_order',
            'price_unit': 101.33,
        }
        self.c_sol_obj.create(line_values)

        # Validate the sale order
        self.c1.exec_workflow('sale.order', 'procurement_validate', self.c_so_id)

        """
        2/ Source the IR to an external partner
        """
        line_ids = self.c_sol_obj.search([('order_id', '=', self.c_so_id)])
        self.c_sol_obj.write(line_ids, {
            'po_cft': 'po',
            'supplier': self.get_record(self.c1, 'ext_supplier_1'),
        })
        self.c_sol_obj.confirmLine(line_ids, run_scheduler=False)

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

        """
        3/ Validate and confirm the PO
        """
        self._validate_po(self.c1, [self.c_po_id])
        self._confirm_po(self.c1, [self.c_po_id])

        """
        4/ Receive 98 PCE
        """
        # Get the IN associated to this PO
        c_in_ids = self.c_pick_obj.search([('purchase_id', '=', self.c_po_id), ('type', '=', 'in')])
        self.assert_(
            len(c_in_ids) == 1,
            "There are %s IN associated to PO - Should be 1" % len(c_in_ids),
        )

        self.c_in_id = c_in_ids[0]

        wiz_res = self.c_pick_obj.action_process(self.c_in_id)
        proc_line_ids = self.c_proc_line_obj.search([('wizard_id', '=', wiz_res['res_id'])])
        self.c_proc_line_obj.write(proc_line_ids, {'quantity': 98.0})
        bo_res = self.c_proc_obj.do_incoming_shipment([wiz_res['res_id']])

    def test_cancel_bo(self):
        """
        Cancel the backorder without resourcing and check the quantity in
        FO line
        """
        # Cancel the back order
        wiz_id = self.c_enter_reason_obj.create({
            'picking_id': self.c_in_id,
            'change_reason': 'test_cancel_bo',
        })
        self.c_enter_reason_obj.do_cancel([wiz_id], {
            'active_ids': [self.c_in_id],
            'cancel_type': 'update_out',
        })

        # Check IN state
        in_state = self.c_pick_obj.read(self.c_in_id, ['state'])['state']
        self.assert_(
            in_state == 'cancel',
            "The BO is not canceled",
        )

        # Check quantity on the original IR line
        sol_ids = self.c_sol_obj.search([('order_id', '=', self.c_so_id)])
        sol_qty = self.c_sol_obj.read(sol_ids[0], ['product_uom_qty'])['product_uom_qty']
        self.assert_(
            sol_qty == 100.0,
            "The quantity on original IR is %s - Should be 100.00" % sol_qty
        )

    def test_resource_bo(self):
        """
        Cancel & Resource the backorder without resourcing and check the
        quantity in FO line
        """
        # Cancel the back order
        wiz_id = self.c_enter_reason_obj.create({
            'picking_id': self.c_in_id,
            'change_reason': 'test_cancel_bo',
        })
        self.c_enter_reason_obj.do_cancel([wiz_id], {
            'active_ids': [self.c_in_id],
            'cancel_type': '',
        })

        # Check IN state
        in_state = self.c_pick_obj.read(self.c_in_id, ['state'])['state']
        self.assert_(
            in_state == 'cancel',
            "The BO is not canceled",
        )

        # Check quantity on the original IR line
        sol_ids = self.c_sol_obj.search([('order_id', '=', self.c_so_id)])
        sol_qty = self.c_sol_obj.read(sol_ids[0], ['product_uom_qty'])['product_uom_qty']
        self.assert_(
            sol_qty == 98.0,
            "The quantity on original IR is %s - Should be 98.00" % sol_qty
        )

        # Check quantity on new IR line
        new_ir_ids = self.c_so_obj.search([('parent_order_name', '=', self.c_so_name), ('procurement_request', '=', True)])
        self.assert_(
            len(new_ir_ids) == 1,
            "No new order created after resourcing",
        )
        sol_ids = self.c_sol_obj.search([('order_id', '=', new_ir_ids[0])])
        sol_qty = self.c_sol_obj.read(sol_ids[0], ['product_uom_qty'])['product_uom_qty']
        self.assert_(
            sol_qty == 2.0,
            "The quantity on original IR is %s - Should be 2.00" % sol_qty
        )

def get_test_class():
    return UTP1007Test
