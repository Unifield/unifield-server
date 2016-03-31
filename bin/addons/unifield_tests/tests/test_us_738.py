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
        self.db = self.p1
        self.order_line_obj = self.db.get('purchase.order.line')
        self.po_obj = self.db.get('purchase.order')
        self.abs_obj = self.db.get('account.bank.statement')
        self.absl_obj = self.db.get('account.bank.statement.line')
        self.pick_obj = self.db.get('stock.picking')
        self.proc_in_obj = self.db.get('stock.incoming.processor')
        self.acc_inv_obj = self.db.get('account.invoice')
        self.stock_move_in_proc = self.db.get('stock.move.in.processor')
        self.import_inv = self.db.get('wizard.import.invoice')
        self.aml_obj = self.db.get('account.move.line')
        self.absl_obj = self.db.get('account.bank.statement.line')

    def create_and_open_bank_register(self):
        nb = self.abs_obj.search_count([])
        reg_code = "US-738-%s" % nb
        register_id, journal_id = self.register_create(self.db, reg_code, reg_code, "bank", "10200", "EUR")
        self.abs_obj.button_open_bank([register_id])
        return register_id

    def create_order_line(self, po_id):
        """
        Add an order line to the PO in parameter, amount 100
        """
        line_values = {
            'order_id': po_id,
            'product_id': self.get_record(self.db, 'prod_log_1'),
            'product_uom': self.get_record(self.db, 'product_uom_unit', module='product'),
            'product_qty': 10.0,
            'type': 'make_to_order',
            'price_unit': 10.00,
        }
        self.order_line_obj.create(line_values)

    def create_and_hard_post_downpayment(self, register_id, po_id, amount):
        partner_id = self.get_record(self.db, 'ext_supplier_1')
        reg_line_id = self.register_create_line(self.db, register_id, '13100', amount, third_partner_id=partner_id)[0]
        self.absl_obj.write(reg_line_id, {'down_payment_id': po_id})
        self.register_line_hard_post(self.db, reg_line_id)

    def process_incoming_shipment(self, po_id, partial=False, qty=0):
        """
        If partial is True, process partial IN of "qty"
        If partial is False, process all IN
        """
        in_ids = self.pick_obj.search([
            ('purchase_id', '=', po_id),
            ('state', '!=', 'done'),
            ('type', '=', 'in'),
        ])
        proc_res = self.pick_obj.action_process(in_ids)
        proc_id = proc_res.get('res_id')
        if partial:
            move_line_id = self.stock_move_in_proc.search([('wizard_id', '=', proc_id)])[0]
            self.stock_move_in_proc.write(move_line_id, {'quantity': qty})
        else:
            self.proc_in_obj.copy_all([proc_id])
        self.proc_in_obj.do_incoming_shipment([proc_id])

    def test_uc1(self):
        """
        USE CASE N°1
        PO amount 100
        DP OUT amount 20
        Process partial IN: 10
        Validate SI: SI must be paid
        Process remaining IN
        Validate SI amount 90: residual must be 80
        """
        # Create, validate and confirm the PO
        self.used_db = self.db
        po_id = ResourcingTest.create_po_from_scratch(self)
        po = self.po_obj.browse(po_id)
        self.create_order_line(po_id)  # amount 100
        self._validate_po(self.db, [po_id])
        self._confirm_po(self.db, [po_id])

        # create the bank register
        register_id = self.create_and_open_bank_register()

        # create and hardpost a DP OUT 20
        self.create_and_hard_post_downpayment(register_id, po_id, -20.00)

        # process partial IN: amount 10
        self.process_incoming_shipment(po_id, True, 1)

        # validate the invoice: the invoice must be paid
        inv_id = self.acc_inv_obj.search([('origin', 'like', '%' + po.name), ('state', '=', 'draft')])[0]
        FinanceTest.invoice_validate(self, self.db, inv_id)
        inv = self.acc_inv_obj.browse(inv_id)
        self.assertEquals(inv.state, 'paid', msg="The first invoice isn't paid")

        # process remaining IN
        self.process_incoming_shipment(po_id)

        # validate SI amount 90, and check the residual amount
        second_inv_id = self.acc_inv_obj.search([('origin', 'like', '%' + po.name), ('state', '=', 'draft')])[0]
        FinanceTest.invoice_validate(self, self.db, second_inv_id)
        second_inv = self.acc_inv_obj.browse(second_inv_id)
        self.assertEquals(second_inv.residual, 80.0,
                          msg="The residual amount isn't correct (%s instead of 80)" % second_inv.residual)

    def test_uc2(self):
        """
        USE CASE N°2
        PO amount 100
        DP OUT amount 20
        DP OUT amount 30
        Process all IN
        Validate SI: residual must be 50
        """
        # Create, validate and confirm the PO
        self.used_db = self.db
        po_id = ResourcingTest.create_po_from_scratch(self)
        po = self.po_obj.browse(po_id)
        self.create_order_line(po_id)  # amount 100
        self._validate_po(self.db, [po_id])
        self._confirm_po(self.db, [po_id])

        # create the bank register
        register_id = self.create_and_open_bank_register()

        # create and hardpost a DP OUT 20, and a DP OUT 30
        self.create_and_hard_post_downpayment(register_id, po_id, -20.00)
        self.create_and_hard_post_downpayment(register_id, po_id, -30.00)

        # process all IN
        self.process_incoming_shipment(po_id)

        # validate the invoice, and check the residual amount
        inv_id = self.acc_inv_obj.search([('origin', 'like', '%' + po.name), ('state', '=', 'draft')])[0]
        FinanceTest.invoice_validate(self, self.db, inv_id)
        inv = self.acc_inv_obj.browse(inv_id)
        self.assertEquals(inv.residual, 50.0,
                          msg="The residual amount isn't correct (%s instead of 50)" % inv.residual)

    def test_uc3(self):
        """
        USE CASE N°3
        PO amount 100
        DP OUT amount 20
        DP OUT amount 30
        Process partial IN: 40
        Validate SI: SI must be paid
        Process remaining IN
        Validate SI: residual must be 50
        Import SI in register, hard post: SI must be paid and PO invoiced
        """
        # Create, validate and confirm the PO
        self.used_db = self.db
        po_id = ResourcingTest.create_po_from_scratch(self)
        po = self.po_obj.browse(po_id)
        self.create_order_line(po_id)  # amount 100
        self._validate_po(self.db, [po_id])
        self._confirm_po(self.db, [po_id])

        # create the bank register
        register_id = self.create_and_open_bank_register()

        # create and hardpost a DP OUT 20, and a DP OUT 30
        self.create_and_hard_post_downpayment(register_id, po_id, -20.00)
        self.create_and_hard_post_downpayment(register_id, po_id, -30.00)

        # process partial IN: amount 40
        self.process_incoming_shipment(po_id, True, 4)

        # validate the invoice: the invoice must be paid
        inv_id = self.acc_inv_obj.search([('origin', 'like', '%' + po.name), ('state', '=', 'draft')])[0]
        FinanceTest.invoice_validate(self, self.db, inv_id)
        inv = self.acc_inv_obj.browse(inv_id)
        self.assertEquals(inv.state, 'paid', msg="The first invoice isn't paid")

        # process remaining IN
        self.process_incoming_shipment(po_id)

        # validate the second SI, and check the residual amount
        second_inv_id = self.acc_inv_obj.search([('origin', 'like', '%' + po.name), ('state', '=', 'draft')])[0]
        FinanceTest.invoice_validate(self, self.db, second_inv_id)
        second_inv = self.acc_inv_obj.browse(second_inv_id)
        self.assertEquals(second_inv.residual, 50.0,
                          msg="The residual amount isn't correct (%s instead of 50)" % second_inv.residual)

        # import SI in register and hard post
        account_move = second_inv.move_id
        aml_ids = self.aml_obj.search([('move_id', '=', account_move.id), ('ready_for_import_in_register', '=', True)])
        wiz_id = self.import_inv.create({'statement_id': register_id, 'line_ids': [(6, 0, aml_ids)]})
        self.import_inv.single_import([wiz_id], {})
        statement_line_id = self.import_inv.action_confirm([wiz_id]).get('st_line_ids')
        self.absl_obj.posting(statement_line_id, 'hard')

        # SI must be paid and PO invoiced
        second_inv = self.acc_inv_obj.browse(second_inv_id)
        self.assertEquals(second_inv.state, 'paid', msg="The second invoice isn't paid")
        po = self.po_obj.browse(po_id)
        self.assertTrue(po.invoiced, "The PO isn't invoiced")


def get_test_class():
    '''Return the class to use for tests'''
    return US738Test
