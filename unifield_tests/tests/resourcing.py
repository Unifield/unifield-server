#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest
from time import strftime
from random import randint
from oerplib import error

import time

class ResourcingTest(UnifieldTest):

    def run_auto_pos_creation(self, db, order_to_check=None):
        """
        Runs the Auto POs creation schedule.
        If 'order_to_check' is defined, check if all lines of the given
        order are confirmed.

        :param db: Cursor to the database
        :param order_to_checK: ID of the order to check

        :return True
        :rtype bool
        """
        # Prepare object
        order_obj = db.get('sale.order')
        proc_obj = db.get('procurement.order')

        pr = order_obj.browse(order_to_check).procurement_request

        new_order_id = None
        if pr:
            state = 'progress'
        else:
            state = 'done'

        order_state = order_obj.read(order_to_check, ['state'])['state']
        while order_state != state:
            time.sleep(0.5)
            order_state = order_obj.read(order_to_check, ['state'])['state']

        if pr:
            new_order_id = order_to_check
        else:
            new_order_ids = order_obj.search([
                ('original_so_id_sale_order', '=', order_to_check)
            ])

            self.assert_(len(new_order_ids) > 0, msg="""
No split of FO found !""")
            if new_order_ids:
                new_order_id = new_order_ids[0]

        proc_obj.run_scheduler()

        return new_order_id


    def _get_order_values(self, db, values=None):
        """
        Returns values for the order

        :param db: Cursor to the database
        :param values: Default values to update

        :return The values for the order
        :rtype dict
        """
        if not values:
            values = {}

        return values

    def create_order(self, db):
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
        prod_log1_id = self.get_record(db, 'prod_log_1')
        prod_log2_id = self.get_record(db, 'prod_log_2')
        prod_med1_id = self.get_record(db, 'prod_med_1')
        prod_med2_id = self.get_record(db, 'prod_med_2')
        uom_pce_id = self.get_record(db, 'product_uom_unit', module='product')

        order_values = self._get_order_values(db)

        order_id = order_obj.create(order_values)

        # Create order lines
        # First line
        line_values = {
            'order_id': order_id,
            'product_id': prod_log1_id,
            'product_uom': uom_pce_id,
            'product_uom_qty': 10.0,
            'type': 'make_to_order',
        }
        line_obj.create(line_values)

        # Second line
        line_values.update({
            'product_id': prod_log2_id,
            'product_uom_qty': 20.0,
        })
        line_obj.create(line_values)

        # Third line
        line_values.update({
            'product_id': prod_med1_id,
            'product_uom_qty': 30.0,
        })
        line_obj.create(line_values)

        # Fourth line
        line_values.update({
            'product_id': prod_med2_id,
            'product_uom_qty': 40.0,
        })
        line_obj.create(line_values)

        return order_id

    def order_source_all_one_po(self, db):
        """
        Create an order and source all lines of this order to a PO (same
        supplier) for all lines.

        :return The ID of the created order, the list of ID of lines of the
                created order, the list of ID of PO created to source the
                order and a list of ID of PO lines created to source the
                order.
        """
        # Prepare object
        order_obj = db.get('sale.order')
        line_obj = db.get('sale.order.line')
        pol_obj = db.get('purchase.order.line')

        # Create the field order
        order_id = self.create_order(db)

        # Source all lines on a Purchase Order to ext_supplier_1
        line_ids = line_obj.search([('order_id', '=', order_id)])
        line_obj.write(line_ids, {
            'po_cft': 'po',
            'supplier': self.get_record(db, 'ext_supplier_1'),
        })
        line_obj.confirmLine(line_ids)

        # Run the scheduler
        new_order_id = self.run_auto_pos_creation(db, order_to_check=order_id)

        line_ids = line_obj.search([('order_id', '=', new_order_id)])
        not_sourced = True
        while not_sourced:
            not_sourced = False
            for line in line_obj.browse(line_ids):
               if line.procurement_id and line.procurement_id.state != 'running':
                    not_sourced = True
            if not_sourced:
                time.sleep(1)

        po_ids = set()
        po_line_ids = []
        for line in line_obj.browse(line_ids):
            if line.procurement_id:
                po_line_ids.extend(pol_obj.search([
                    ('procurement_id', '=', line.procurement_id.id),
                ]))

        for po_line in pol_obj.read(po_line_ids, ['order_id']):
            po_ids.add(po_line['order_id'][0])

        return new_order_id, line_ids, list(po_ids), po_line_ids

    def _validate_po(self, db, po_ids):
        """
        Check if the PO are in 'draft' state.
        Then, validate them.
        Then, check if all PO are now in 'confirmed' state.

        :param db: Connection to the database
        :param po_ids: List of ID of purchase.order to validate
        :return The list of ID of purchase.order validated
        """
        # Prepare object
        po_obj = db.get('purchase.order')
        pol_obj = db.get('purchase.order.line')

        # Add an analytic distribution on PO lines that have no
        no_ana_line_ids = pol_obj.search([
            ('order_id', 'in', po_ids),
            ('analytic_distribution_id', '=', False),
        ])
        pol_obj.write(no_ana_line_ids, {
            'analytic_distribution_id': self.get_record(db, 'distrib_1'),
        })

        # Check if the PO is draft
        for po_id in po_ids:
            po_state = po_obj.read(po_id, ['state'])['state']
            self.assert_(po_state == 'draft', msg="""
The state of the generated PO is %s - Should be 'draft'""" % po_state)
            # Validate the PO
            db.exec_workflow('purchase.order', 'purchase_confirm', po_id)
            po_state = po_obj.browse(po_id).state
            self.assert_(po_state == 'confirmed', msg="""
The state of the generated PO is %s - Should be 'confirmed'""" % po_state)

        return po_ids

    def _confirm_po(self, db, po_ids, dcd=None):
        """
        1/ Check if the PO are in 'confirrmed' state
        2/ Confirm them
        3/ Check if all PO are now in 'assigned' state
        :param db: Connection to the database
        :param po_ids: List of ID of purchase.order to confirm
        :param dcd: Delivery confirmed date to set
        :return: The list of ID of purchase.order confirmed
        """
        # Prepare object
        po_obj = db.get('purchase.order')

        if not dcd:
            dcd = time.strftime('%Y-%m-%d')

        po_obj.write(po_ids, {'delivery_confirmed_date': dcd})

        for po_id in po_ids:
            """
            1/ Check if the PO are in 'confirmed' state
            """
            po_state = po_obj.read(po_id, ['state'])['state']
            self.assert_(
                po_state == 'confirmed',
                "The state of the generated PO is %s - Should be 'confirmed'" % po_state,
            )
            """
            2/ Confirm the PO
            """
            po_obj.confirm_button([po_id])
            """
            3/ Check if all PO are now in 'approved' state
            """
            po_state = po_obj.read(po_id, ['state'])['state']
            self.assert_(
                po_state == 'approved',
                "The state of the generated PO is %s - Should be 'approved'" % po_state,
            )

        return po_ids

    def _get_number_of_valid_lines(self, db, order_id):
        raise NotImplementedError

    def test_uf_2507(self):
        """
        1/ Create a field order with 4 lines and source all lines
        in the same PO.
        2/ Delete the first line.
        3/ Add a new line without origin set
        4/ Set the origin on the new line
        5/ Validate and confirm the PO
        6/ Check the number of lines in the FO
        """
        db = self.c1

        # Prepare object
        c_wiz_model = 'purchase.order.line.unlink.wizard'

        order_obj = db.get('sale.order')
        pol_obj = db.get('purchase.order.line')
        po_obj = db.get('purchase.order')
        c_wiz = db.get(c_wiz_model)

        """
        1/ Create and source the first FO
        """
        order_id, order_line_ids, po_ids, po_line_ids = self.\
            order_source_all_one_po(db)

        # Check number of generated PO and PO lines
        self.assertEqual(
            len(po_ids),
            1,
            "Number of generated PO : %s - Should be 1" % len(po_ids),
        )
        self.assertEqual(
            len(po_line_ids),
            4,
            "Number of lines generated in PO : %s - Should be 4" % len(po_line_ids),
        )

        """
        2/ Delete the first line of the PO
        """
        c_res = pol_obj.ask_unlink(po_line_ids[0])

        # Check display of cancel wizard
        self.assert_(
            c_res.get('res_id'),
            "No wizard returned by the cancellation of the PO line",
        )
        self.assert_(
            c_res.get('res_model') == c_wiz_model,
            "The model returned by the cancellation of the PO line is not good",
        )

        c_wiz.just_cancel(c_res.get('res_id'))

        # Check the PO line has been removed
        po_line_ids = po_obj.read(po_ids[0], ['order_line'])['order_line']
        self.assert_(
            len(po_line_ids) == 3,
            "The line has not been removed well on the PO (%s - should be 3)" % len(po_line_ids),
        )
        # Check the FO line has been removed
        self.assert_(
            self._get_number_of_valid_lines(db, order_id) == 3,
            "The line has not been removed well on the FO",
        )

        """
        3/ Add a new line without origin set
        """
        ana_distrib_id = pol_obj.read(po_line_ids[1], ['analytic_distribution_id'])['analytic_distribution_id']
        if not ana_distrib_id:
            ana_distrib_id = self.get_record(db, 'distrib_1')
        else:
            ana_distrib_id = ana_distrib_id[0]
        line_values = {
            'order_id': po_ids[0],
            'product_id': self.get_record(db, 'prod_log_1'),
            'product_uom': self.get_record(db, 'product_uom_unit', module='product'),
            'product_qty': 123,
            'price_unit': 01.20,
            'analytic_distribution_id': ana_distrib_id,
        }
        new_pol_id = pol_obj.create(line_values)

        # Check the PO line has been added well
        po_line_ids = po_obj.read(po_ids[0], ['order_line'])['order_line']
        self.assert_(
            len(po_line_ids) == 4,
            "Number of lines generated in PO : %s - Should be 4" % len(po_line_ids),
        )

        """
        4/ Set the origin on the new line
        """
        order_name = order_obj.read(order_id, ['name'])['name']
        pol_obj.write(new_pol_id, {'origin': order_name})

        """
        5/ Validate and confirm the PO
        """
        self._validate_po(db, po_ids)
        self._confirm_po(db, po_ids)

        """
        6/ Check the number of lines in the FO/IR
        """
        # Check the FO line has been added
        fo_lines_nb = self._get_number_of_valid_lines(db, order_id)
        self.assert_(
            fo_lines_nb == 4,
            "The line has not been added well on the order (%s - should be 4)" % fo_lines_nb,
        )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
