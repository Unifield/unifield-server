#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest

import time


class UFTP326Test(ResourcingTest):

    def setUp(self):
        """
        Create a PO at Project side to Coordo with
        two lines.
        :return:
        """
        super(UFTP326Test, self).setUp()

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

        # Prepare values for the field order
        prod_log1_id = self.get_record(self.c1, 'prod_log_1')
        prod_log2_id = self.get_record(self.c1, 'prod_log_2')
        uom_pce_id = self.get_record(self.c1, 'product_uom_unit', module='product')

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
            'procurement_request': False,
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

        self.synchronize(self.c1)
        self.synchronize(self.p1)
        self.synchronize(self.c1)

        # P1
        self.p_so_obj = self.p1.get('sale.order')
        self.p_sol_obj = self.p1.get('sale.order.line')
        self.p_po_obj = self.p1.get('purchase.order')
        self.p_pol_obj = self.p1.get('purchase.order.line')
        self.p_partner_obj = self.p1.get('res.partner')
        self.p_lc_obj = self.p1.get('sale.order.leave.close')
        self.p_so_cancel_obj = self.p1.get('sale.order.cancelation.wizard')

        self.p_po_id = None

        p_po_ids = self.p_po_obj.search([('partner_ref', 'like', self.c_so_name)])
        for p_po_id in p_po_ids:
            self.assert_(
                self.p_po_obj.read(p_po_id, ['state'])['state'] == 'sourced',
                "The PO at Project is '%s' - Should be 'sourced'." % self.p_po_obj.read(p_po_id, ['state'])['state'],
            )
            self.p_po_id = p_po_id

    def test_cancel_po_at_coordo(self):
        """
        Cancel the PO at coordo side.
        Check if the PO at project side is canceled.
        :return:
        """
        wiz_model = 'purchase.order.cancel.wizard'
        c_wiz_obj = self.c1.get(wiz_model)
        c_lc_wiz_obj = self.c1.get('sale.order.leave.close')
        c_cancel_so_wiz_obj = self.c1.get('sale.order.cancelation.wizard')

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

    def cancel_or_resource_in_at_coordo(self, resource=False):
        """
        Cancel or Cancel & Resource the IN at coordo side.
        Check if the PO and the FO at coordo side are canceled.
        Check if the PO at project side is canceled.
        :return:
        """
        # Validate and confirm the PO
        self._validate_po(self.c1, [self.c_po_id])
        self._confirm_po(self.c1, [self.c_po_id])

        # Get the IN associated to this PO
        c_in_ids = self.c_pick_obj.search([('purchase_id', '=', self.c_po_id), ('type', '=', 'in')])
        c_out_ids = self.c_pick_obj.search([('sale_id', '=', self.c_so_id), ('type', '=', 'out')])
        self.assert_(
            len(c_in_ids) == 1,
            "There are %s IN associated to PO - Should be 1" % len(c_in_ids),
        )
        self.assert_(
            len(c_out_ids) == 1,
            "There are %s OUT/PICK associated to FO - Should be 1" % len(c_out_ids),
        )

        # Cancel the IN
        wiz_id = self.c_enter_reason_obj.create({
            'picking_id': c_in_ids[0],
            'change_reason': 'test_cancel_in_at_coordo',
        })
        ctx = {
            'active_ids': c_in_ids,
        }
        if not resource:
            ctx['cancel_type'] = 'update_out'

        self.c_enter_reason_obj.do_cancel([wiz_id], ctx)

        # Check IN and OUT states
        in_state = self.c_pick_obj.read(c_in_ids, ['state'])
        out_state = self.c_pick_obj.read(c_out_ids, ['state'])
        self.assert_(
            all([x['state'] == 'cancel' for x in in_state]),
            "All IN are not canceled",
        )
        self.assert_(
            all([x['state'] == 'done' for x in out_state]),
            "All OUT/PICK are not canceled",
        )

        # Check PO state
        po_state = self.c_po_obj.read(self.c_po_id, ['state'])['state']
        self.assert_(
            po_state == 'done',
            "The PO state is '%s' - Should be 'done'" % po_state,
        )

        # Check FO state
        fo_state = self.c_so_obj.read(self.c_so_id, ['state'])['state']
        self.assert_(
            fo_state == 'done',
            "The FO state is '%s' - Should be 'done'" % fo_state,
        )

    def test_cancel_in_at_coordo(self):
        """
        Cancel the IN at coordo side.
        Check if the PO and the FO at coordo side are canceled.
        Check if the PO at project side is canceled.
        :return:
        """
        self.cancel_or_resource_in_at_coordo()

    def test_resource_in_at_coordo(self):
        """
        Cancel & Resource the IN at coordo side.
        Check if the PO and the FO at coordo side are canceled.
        Check if the PO at project side is canceled.
        :return:
        """
        self.cancel_or_resource_in_at_coordo(resource=True)

def get_test_class():
    return UFTP326Test
