#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from test_uf_2490_one_po import ResourcingTest

import time


class UF2490OneTender(ResourcingTest):

    def create_tender_from_scratch(self):
        """
        Create a tender from scratch
        :return:
        """
        db = self.used_db

        # Create tender
        self.tender_id = self.tender_obj.create({
            'location_id': self.get_record(db, 'stock_location_stock', module='stock'),
        })

    def create_tender_line(self):
        """
        Create a tender line on the test tender
        :return:
        """
        db = self.used_db

        # Create tender line
        self.tender_line_id = self.tender_line_obj.create({
            'tender_id': self.tender_id,
            'product_id': self.get_record(db, 'prod_log_1'),
            'product_uom': self.get_record(db, 'product_uom_unit', module='product'),
        })

    def test_cancel_empty_tender_from_scratch(self):
        """
        Create a tender without line and cancel it
        :return:
        """
        self.create_tender_from_scratch()
        # Cancel the tender
        res = self.tender_obj.cancel_tender(self.tender_id)
        if isinstance(res, dict):
            self.assert_(
                res.get('res_model', False) != 'tender.cancel.wizard',
                "A wizard that asks user to re-source need is displayed and shouldn't",
            )

        tender_state = self.tender_obj.read(self.tender_id, ['state'])['state']
        self.assert_(
            tender_state == 'cancel',
            "The tender is in state '%s' - Should be 'cancel'" % tender_state,
        )

    def test_cancel_tender_from_scratch(self):
        """
        Crate a tender with one line and cancel the tender
        :return:
        """
        self.create_tender_from_scratch()
        # Create a line
        self.create_tender_line()

        # Cancel the tender
        res = self.tender_obj.cancel_tender(self.tender_id)
        if isinstance(res, dict):
            self.assert_(
                res.get('res_model', False) != 'tender.cancel.wizard',
                "A wizard that asks user to re-source need is displayed and shouldn't",
            )

        tender_state = self.tender_obj.read(self.tender_id, ['state'])['state']
        self.assert_(
            tender_state == 'cancel',
            "The tender is in state '%s' - Should be 'cancel'" % tender_state,
        )

    def test_cancel_tender_line_from_scratch(self):
        """
        Create a tender with one line and cancel the line
        :return:
        """
        self.create_tender_from_scratch()
        # Create a line
        self.create_tender_line()

        # Cancel the tender line
        res = self.tender_line_obj.ask_unlink(self.tender_line_id)
        self.assert_(
            isinstance(res, dict) and res.get('res_id', False) and res.get('res_model', False) == 'tender.cancel.wizard',
            "No wizard displayed to check if the tender should be canceled or not",
        )

        self.used_db.get('tender.cancel.wizard').just_cancel(res.get('res_id'))

        # Check state of the tender
        tender_state = self.tender_obj.read(self.tender_id, ['state'])['state']
        self.assert_(
            tender_state == 'cancel',
            "The state of the tender is '%s' - Should be 'cancel'" % tender_state,  
        )

class UF2490FOOneTender(UF2490OneTender):

    def setUp(self):
        self.pr = False
        super(UF2490FOOneTender, self).setUp()


class UF2490IROneTender(UF2490OneTender):

    def setUp(self):
        self.pr = True
        super(UF2490IROneTender, self).setUp()


def get_test_suite():
    return UF2490IROneTender, UF2490FOOneTender