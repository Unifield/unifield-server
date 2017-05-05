#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest
from oerplib.error import RPCError

import time


class UTP1220Test(UnifieldTest):

    def setUp(self):
        self.used_db = self.c1
        db = self.used_db
        self.po_obj = db.get('purchase.order')
        self.pol_obj = db.get('purchase.order.line')
        self.rfq_id = None
        self.po_id = None

    def tearDown(self):
        """
        Done the generated documents
        :return:
        """
        db = self.used_db
        ddw_obj = db.get('documents.done.wizard')
        ddp_obj = db.get('documents.done.problem')

        # Done the RfQ
        if self.rfq_id:
            ddw_ids = ddw_obj.search([
                ('res_id', '=', self.rfq_id),
                ('model', '=', 'purchase.order'),
            ])
            if ddw_ids:
                ddw_res = ddw_obj.go_to_problems([ddw_ids[0]])
                if ddw_res and isinstance(ddw_res, dict):
                    ddp_obj.cancel_document([ddw_res.get('res_id')])
            elif self.po_obj.browse(self.rfq_id).state == 'draft':
                self.po_obj.unlink(self.rfq_id)

        # Done the PO
        if self.po_id:
            ddw_ids = ddw_obj.search([
                ('res_id', '=', self.po_id),
                ('model', '=', 'purchase.order'),
            ])
            if ddw_ids:
                ddw_res = ddw_obj.go_to_problems([ddw_ids[0]])
                if ddw_res and isinstance(ddw_res, dict):
                    ddp_obj.cancel_document([ddw_res.get('res_id')])
            elif self.po_obj.browse(self.po_id).state == 'draft':
                self.po_obj.unlink(self.po_id)

    def test_create_rfq_from_scratch(self):
        """
        Create a RfQ from scratch with three lines.
        """
        partner_id = self.get_record(self.used_db, 'supplier1')
        location_id = self.get_record(
            self.used_db,
            'stock_location_stock',
            'stock',
        )
        wh_id = self.get_record(
            self.used_db,
            'warehouse0',
            'stock',
        )

        rfq_values = {
            'partner_id': partner_id,
            'rfq_ok': True,
            'warehouse_id': wh_id,
            'location_id': location_id,
        }
        vals_on_change = self.po_obj.onchange_partner_id(
            None,
            partner_id,
            time.strftime('%Y-%m-%d'),
            False,
            {},
        )
        rfq_values.update(vals_on_change['value'])
        self.rfq_id = self.po_obj.create(rfq_values)

        # Add two lines
        prod1_id = self.get_record(self.used_db, 'prod_log_1')
        prod2_id = self.get_record(self.used_db, 'prod_log_2')
        uom_id = self.get_record(
            self.used_db,
            'product_uom_unit',
            'product',
        )

        line1_values = {
            'product_id': prod1_id,
            'product_qty': 10.0,
            'product_uom': uom_id,
            'price_unit': 0.00,
            'order_id': self.rfq_id,
        }
        self.rfql1_id = self.pol_obj.create(line1_values)

        line2_values = {
            'product_id': prod2_id,
            'product_qty': 20.0,
            'product_uom': uom_id,
            'price_unit': 0.00,
            'order_id': self.rfq_id,
        }
        self.rfql2_id = self.pol_obj.create(line2_values)

        self.po_obj.rfq_sent(self.rfq_id)

        self.pol_obj.write(self.rfql2_id, {
            'price_unit': 10.00,
            })

        self.po_obj.write(self.rfq_id, {
            'valid_till': time.strftime('%Y-%m-%d'),
        })

        # Update the RfQ
        try:
            self.po_obj.check_rfq_updated(self.rfq_id)
            self.assertTrue(
                False,
                "The RfQ is updated even if there is a line without price",
            )
        except RPCError, e:
            self.pol_obj.ask_unlink(self.rfql1_id)

        try:
            self.po_obj.check_rfq_updated(self.rfq_id)
        except RPCError, e:
            self.assertTrue(
                False,
                "The RfQ is updated even if the line was canceled",
            )

        # Generate PO
        self.po_id = self.po_obj.generate_po_from_rfq(self.rfq_id)

        # Check number of lines in generated PO
        pol_ids = self.pol_obj.search([('order_id', '=', self.po_id)])
        self.assert_(
            len(pol_ids) == 1,
            "The generated PO must have only 1 line (res: %s)" % len(pol_ids),
        )

def get_test_class():
    return UTP1220Test

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
