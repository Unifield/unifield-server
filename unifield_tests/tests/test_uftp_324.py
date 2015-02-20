#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest

import time


class UFTP324Test(ResourcingTest):

    def setUp(self):
        """
        Create a PO at Project side to Coordo with
        two lines.
        :return:
        """

        super(UFTP324Test, self).setUp()

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

        # P1
        self.p_so_obj = self.p1.get('sale.order')
        self.p_sol_obj = self.p1.get('sale.order.line')
        self.p_po_obj = self.p1.get('purchase.order')
        self.p_pol_obj = self.p1.get('purchase.order.line')
        self.p_partner_obj = self.p1.get('res.partner')
        self.p_lc_obj = self.p1.get('sale.order.leave.close')
        self.p_so_cancel_obj = self.p1.get('sale.order.cancelation.wizard')

        # Create a PO at P1 with two products to C1
        # Prepare values for the field order
        prod_log1_id = self.get_record(self.p1, 'prod_log_1')
        prod_log2_id = self.get_record(self.p1, 'prod_log_2')
        uom_pce_id = self.get_record(self.p1, 'product_uom_unit', module='product')
        location_id = self.get_record(self.p1, 'stock_location_stock', module='stock')

        partner_name = self.get_db_partner_name(self.c1)
        partner_ids = self.p_partner_obj.search([('name', '=', partner_name)])
        self.assert_(
            partner_ids,
            "No partner found for %s" % self.c1.db_name,
        )

        distrib_id = self.create_analytic_distribution(self.p1)

        order_values = {
            'order_type': 'regular',
            'partner_id': partner_ids[0],
            'rfq_ok': False,
            'location_id': location_id,
            'analytic_distribution_id': distrib_id,
        }

        change_vals = self.p_po_obj.\
            onchange_partner_id(None, partner_ids[0], time.strftime('%Y-%m-%d')).get('value', {})
        order_values.update(change_vals)

        self.p_po_id = self.p_po_obj.create(order_values)

        # Create order lines
        # First line
        line_values = {
            'order_id': self.p_po_id,
            'product_id': prod_log1_id,
            'product_uom': uom_pce_id,
            'product_qty': 10.0,
            'price_unit': 10.00,
            'type': 'make_to_order',
        }
        self.p_pol_obj.create(line_values)

        # Second line
        line_values.update({
            'product_id': prod_log2_id,
            'product_uom_qty': 20.0,
            'price_unit': 10.0,
        })
        self.p_pol_obj.create(line_values)

        # Validate the sale order
        self.p1.exec_workflow('purchase.order', 'purchase_confirm', self.p_po_id)

        self.p_po_name = self.p_po_obj.read(self.p_po_id, ['name'])['name']

        # Synchronize
        self.synchronize(self.p1)
        self.synchronize(self.c1)

        self.c_so_id = None

        c_so_ids = self.c_so_obj.search([('client_order_ref', 'like', self.p_po_name)])
        for c_so_id in c_so_ids:
            self.assert_(
                self.c_so_obj.read(c_so_id, ['state'])['state'] == 'draft',
                "The FO at Coordo is not 'Draft'.",
            )
            self.c_so_id = c_so_id

        # Validate the sale order
        self.c1.exec_workflow('sale.order', 'order_validated', self.c_so_id)

    def test_utp_324(self):
        """
        Cancel the PO at coordo side, synchronize and check the state of the PO at
        project side.
        :return:
        """
        wiz_model = 'purchase.order.cancel.wizard'
        c_wiz_obj = self.c1.get(wiz_model)
        c_lc_wiz_obj = self.c1.get('sale.order.leave.close')
        c_cancel_so_wiz_obj = self.c1.get('sale.order.cancelation.wizard')
        
        # Source all lines on a Purchase Order to ext_supplier_1
        line_ids = self.c_sol_obj.search([('order_id', '=', self.c_so_id)])
        self.c_sol_obj.write(line_ids, {
            'type': 'make_to_order',
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

            self.c_po_id = po_line['order_id'][0]

        # Cancel PO at coordo side
        c_res = self.c_po_obj.purchase_cancel(self.c_po_id)
        # Validate cancellation
        w_res = c_wiz_obj.cancel_po(c_res.get('res_id'))
        # Close the FO
        w_line_ids = c_lc_wiz_obj.search([
            ('wizard_id', '=', w_res.get('res_id')),
            ('order_id', '=', self.c_so_id),
        ])


        # Choose close it
        c_lc_wiz_obj.write(w_line_ids, {'action': 'close'})
        c_cancel_so_wiz_obj.close_fo(w_res.get('res_id'))

        self.synchronize(self.c1)
        self.synchronize(self.p1)

        # Check state of the PO at project side
        c_so_name = self.c_so_obj.read(self.c_so_id, ['name'])['name']
        self.p_po_id = self.p_po_obj.search([('partner_ref', 'like', c_so_name)])[0]
        p_po_state = self.p_po_obj.read(self.p_po_id, ['state'])['state']
        self.assert_(
            p_po_state == 'done',
            "The PO at project side is not closed",
        )
        # Check number of lines in PO at project side
        p_po_line_ids = self.p_pol_obj.search([('order_id', '=', self.p_po_id)])
        self.assert_(
            len(p_po_line_ids) == 0,
            "There is always lines in PO at project side"
        )

def get_test_class():
    return UFTP324Test
