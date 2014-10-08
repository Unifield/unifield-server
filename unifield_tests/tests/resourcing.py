#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest
from time import strftime
from random import randint
from oerplib import error


class ResourcingTest(UnifieldTest):

    def create_order(self, db, pr=False):
        """
        Create a field order or an internal request (sale.order) with 4 lines:
          - 2 lines with LOG products:
            - 1 line with 10 PCE
            - 1 line with 20 PCE
          - 2 lines with MED products:
            - 1 line with 30 PCE
            - 1 line with 40 PCE

        :param db: Connection to the database
        :param pr: True if we want to create an Internal request, False if we
                   want to create a Field Order

        :return The ID of the new Internal request or field orde
        :rtype int
        """
        # Prepare some objects
        order_obj = db.get('sale.order')
        line_obj = db.get('sale.order.line')

        # Prepare values for the field order
        prod_log1_id = self.get_test_obj(db, 'prod_log_1')
        prod_log2_id = self.get_test_obj(db, 'prod_log_2')
        prod_med1_id = self.get_test_obj(db, 'prod_med_1')
        prod_med2_id = self.get_test_obj(db, 'prod_med_2')

        partner_id = False
        p_addr_id = False
        if not pr:
            partner_id = self.get_test_obj(db, 'ext_customer_1')
            p_addr_id = self.get_test_obj(db, 'ext_customer_1_addr')

        order_id = order_obj.create({
            'procurement_request': pr,
            'partner_id': partner_id,
        })

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
