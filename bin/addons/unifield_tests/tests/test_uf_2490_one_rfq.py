#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from test_uf_2490_one_po import UF2490OnePO

import time

class UF2490OneRfQ(UF2490OnePO):

    def create_po_from_scratch(self):
        """
        Create a RfQ from scratch, then cancel it.
        :return: The ID of the new request for quotation
        """
        db = self.used_db

        # Create PO
        partner_id = self.get_record(db, 'ext_supplier_1')
        po_values = {
            'rfq_ok': True,
            'partner_id': partner_id,
            'partner_address_id': self.get_record(db, 'ext_supplier_1_addr'),
            'location_id': self.get_record(db, 'stock_location_stock', module='stock'),
        }
        po_values.update(
            self.po_obj.onchange_partner_id(None, partner_id, time.strftime('%Y-%m-%d'), None, None).get('value', {})
        )
        po_id = self.po_obj.create(po_values)

        return po_id

    def order_source_all_one_rfq(self, db):
        """
        Create an order and source all lines of this order to a RfQ (same
        supplier) for all lines.

        :return The ID of the created order, the list of ID of lines of the
                created order, the list of ID of RfQ created to source the
                order and a list of ID of RfQ lines created to source the
                order.
        """
        # Create the field order
        order_id = self.create_order(db)

        # Source all lines on a Purchase Order to ext_supplier_1
        line_ids = self.order_line_obj.search([('order_id', '=', order_id)])
        self.order_line_obj.write(line_ids, {
            'po_cft': 'rfq',
            'supplier': self.get_record(db, 'ext_supplier_1'),
        })
        self.order_line_obj.confirmLine(line_ids)

        # Run the scheduler
        new_order_id = self.run_auto_pos_creation(db, order_to_check=order_id)

        line_ids = self.order_line_obj.search([('order_id', '=', new_order_id)])
        not_sourced = True
        while not_sourced:
            not_sourced = False
            for line in self.order_line_obj.browse(line_ids):
               if line.procurement_id and line.procurement_id.state != 'rfq':
                    not_sourced = True
            if not_sourced:
                time.sleep(1)

        po_ids = set()
        po_line_ids = []
        for line in self.order_line_obj.browse(line_ids):
            if line.procurement_id:
                po_line_ids.extend(self.pol_obj.search([
                    ('procurement_id', '=', line.procurement_id.id),
                ]))

        for po_line in self.pol_obj.read(po_line_ids, ['order_id']):
            po_ids.add(po_line['order_id'][0])

        return new_order_id, line_ids, list(po_ids), po_line_ids

    def create_order_and_source(self):
        """
        Create a FO/IR with 4 lines, source it to a Po
        :return:
        """
        fo_id, fo_line_ids, po_ids, pol_ids = self.order_source_all_one_rfq(self.used_db)
        self.order_id = fo_id
        self.po_id = po_ids[0]
        self.pol_ids = pol_ids

    # #########
    #
    #  Begin of tests
    #
    ##########

    def test_cancel_validated_po_from_scracth(self):
        """
        Create a RfQ from scratch, add a line on the RfQ,
        validate it, then cancel it
        """
        db = self.used_db

        # Create PO
        po_id = self.create_po_from_scratch()

        # Create PO line
        self.create_po_line(po_id)

        # Add an analytic distribution on the PO
        ad_id = self.get_record(db, 'distrib_1')
        self.po_obj.write(po_id, {'analytic_distribution_id': ad_id})

        # Validate the PO
        self.po_obj.rfq_sent(po_id)

        # Cancel the PO
        self.cancel_po(po_id)


class UF2490FOOneRfQ(UF2490OneRfQ):

    def setUp(self):
        self.pr = False
        super(UF2490FOOneRfQ, self).setUp()


class UF2490IROneRfQ(UF2490OneRfQ):

    def setUp(self):
        self.pr = True
        super(UF2490IROneRfQ, self).setUp()

    def test_create_order_cancel_po_leave_order(self):
        pass

    def test_create_order_cancel_po_close_order(self):
        pass


def get_test_suite():
    '''Return the class to use for tests'''
    return UF2490FOOneRfQ, UF2490IROneRfQ
