#!/usr/bin/env python
# -*- coding: utf8 -*-

from resourcing import ResourcingTest
from finance import FinanceTest


class US738Test(ResourcingTest, FinanceTest):
    """
    Tests on down payments
    """

    def setUp(self):
        super(US738Test, self).setUp()

    def test_uc2(self):
        """
        USE CASE N°2
        PO amount 100
        DP OUT amount 20
        DP OUT amount 30
        Process all IN
        Validate SI: residual must be 50
        """
        db = self.p1
        # Create the PO
        self.used_db = db
        self.po_obj = db.get('purchase.order')
        po_id = ResourcingTest.create_po_from_scratch(self)
        po = self.po_obj.browse(po_id)

        # create an order line
        order_line_obj = db.get('purchase.order.line')
        line_values = {
            'order_id': po_id,
            'product_id': self.get_record(db, 'prod_log_1'),
            'product_uom': self.get_record(db, 'product_uom_unit', module='product'),
            'product_qty': 10.0,
            'type': 'make_to_order',
            'price_unit': 10.00,
        }
        order_line_obj.create(line_values)

        # validate and confirm the PO
        self._validate_po(db, [po_id])
        self._confirm_po(db, [po_id])

        # create the bank register
        abs_obj = db.get('account.bank.statement')
        nb = abs_obj.search_count([])
        reg_code = "US-738-%s" % nb
        register_id, journal_id = self.register_create(db, reg_code, reg_code, "bank", "10200", "EUR")
        abs_obj.button_open_bank([register_id])

        # create a DP OUT 20
        absl_obj = db.get('account.bank.statement.line')
        partner_id = self.get_record(db, 'ext_supplier_1')
        reg_line_id = self.register_create_line(db, register_id, '13100', -20.00, third_partner_id=partner_id)[0]
        absl_obj.write(reg_line_id, {'down_payment_id': po_id})
        # hard post
        self.register_line_hard_post(db, reg_line_id)

        # create a DP OUT 30
        reg_line_id = self.register_create_line(db, register_id, '13100', -30.00, third_partner_id=partner_id)[0]
        absl_obj.write(reg_line_id, {'down_payment_id': po_id})
        # hard post
        self.register_line_hard_post(db, reg_line_id)

        # process all IN
        pick_obj = db.get('stock.picking')
        proc_in_obj = db.get('stock.incoming.processor')
        in_ids = pick_obj.search([
            ('purchase_id', '=', po_id),
            ('state', '!=', 'done'),
            ('type', '=', 'in'),
        ])
        proc_res = pick_obj.action_process(in_ids)
        proc_id = proc_res.get('res_id')
        proc_in_obj.copy_all([proc_id])
        proc_in_obj.do_incoming_shipment([proc_id])

        # validate the invoice
        acc_inv_obj = db.get("account.invoice")
        inv_id = acc_inv_obj.search([('origin', 'like', '%' + po.name)])[0]
        inv = acc_inv_obj.browse(inv_id)
        FinanceTest.invoice_validate(self, db, inv_id)

        # check the residual amount
        self.assertEquals(inv.residual, 50.0, msg="The residual amount isn't correct (%s instead of 50)"  % inv.residual)


def get_test_class():
    '''Return the class to use for tests'''
    return US738Test
