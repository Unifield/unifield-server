#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest
from oerplib.error import RPCError

import time


class FOTest(UnifieldTest):

    def setUp(self):
        self.used_db = self.c1
        db = self.used_db
        self.fo_obj = db.get('sale.order')
        self.fol_obj = db.get('sale.order.line')

    def test_validation_no_price_unit(self):
        """
        Create a FO with two lines. One of these lines have no price unit.
        Expected result: An error must be raised
        """
        partner_id = self.get_record(self.used_db, 'ext_customer_1')
        order_type = 'regular'

        # Get the analytic distribution
        distrib_id = self.get_record(self.used_db, 'distrib_1')

        order_values = self.fo_obj.\
            onchange_partner_id(None, partner_id, order_type).get('value', {})
        order_values.update({
            'order_type': order_type,
            'procurement_request': False,
            'partner_id': partner_id,
            'ready_to_ship_date': time.strftime('%Y-%m-%d'),
            'analytic_distribution_id': distrib_id,
        })
        order_id = self.fo_obj.create(order_values)

        # Create order lines
        prod_log1_id = self.get_record(self.used_db, 'prod_log_1')
        prod_log2_id = self.get_record(self.used_db, 'prod_log_2')
        uom_pce_id = self.get_record(
            self.used_db,
            'product_uom_unit',
            module='product'
        )

        line_values = {
            'order_id': order_id,
            'product_id': prod_log1_id,
            'product_uom': uom_pce_id,
            'product_uom_qty': 10.0,
            'type': 'make_to_order',
            'price_unit': 10.0,
        }
        self.fol_obj.create(line_values)

        line_values.update({
            'product_id': prod_log2_id,
            'price_unit': 0.0,
        })
        self.fol_obj.create(line_values)

        try:
            self.c1.exec_workflow('sale.order', 'order_validated', order_id)
            self.assert_(
                False,
                'No error message at FO validation with line with no price.',
            )
        except RPCError as e:
            return True


def get_test_class():
    return FOTest
