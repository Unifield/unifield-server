#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest

import time

class ResourcingTest(UnifieldTest):

    def setUp(self):
        self.used_db = self.c1
        db = self.used_db
        self.order_obj = db.get('sale.order')
        self.order_line_obj = db.get('sale.order.line')
        self.po_obj = db.get('purchase.order')
        self.pol_obj = db.get('purchase.order.line')
        self.proc_obj = db.get('procurement.order')
        self.data_obj = db.get('ir.model.data')
        self.tender_obj = db.get('tender')
        self.tender_line_obj = db.get('tender.line')

        if not hasattr(self, 'pr'):
            self.pr = False

    def tearDown(self):
        """
        Done all remaining documents
        :return:
        """
        db = self.used_db

        ddw_obj = db.get('documents.done.wizard')
        ddp_obj = db.get('documents.done.problem')

        ddw_ids = ddw_obj.search([])
        while ddw_ids:
            ddw_res = ddw_obj.go_to_problems([ddw_ids[0]])
            if ddw_res and isinstance(ddw_res, dict):
                ddp_obj.cancel_document([ddw_res.get('res_id')])

            ddw_ids = ddw_obj.search([])


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

    def _get_fo_values(self, db, values=None):
        """
        Returns specific values for a Field order (partner, partner address,
        pricelist...)

        :param db: Cursor to the database
        :param values: Default values to update

        :return The values of the order
        :rtype dict
        """
        if values is None:
            values = {}

        # Prepare values for the field order
        partner_id = self.get_record(db, 'ext_customer_1')
        order_type = 'regular'

        change_vals = self.order_obj.\
            onchange_partner_id(None, partner_id, order_type).get('value', {})
        values.update(change_vals)

        # Add an analytic distribution
        distrib_id = self.create_analytic_distribution(db)

        values.update({
            'order_type': order_type,
            'procurement_request': False,
            'partner_id': partner_id,
            'ready_to_ship_date': time.strftime('%Y-%m-%d'),
            'analytic_distribution_id': distrib_id,
        })

        return values

    def _get_ir_values(self, db, values=None):
        """
        Returns specific values for an Internal Request

        :param db: Cursor to the database
        :param values: Default values to update

        :return The values of the internal request
        :rtype dict
        """
        if values is None:
            values = {}

        location_id = self.data_obj.get_object_reference(
            'stock',
            'stock_location_stock',
        )[1]

        values.update({
            'procurement_request': True,
            'location_requestor_id': location_id,
        })

        return values

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

        if self.pr:
            values = self._get_ir_values(db, values)
        else:
            values = self._get_fo_values(db, values)

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

        # Prepare values for the field order
        prod_log1_id = self.get_record(db, 'prod_log_1')
        prod_log2_id = self.get_record(db, 'prod_log_2')
        prod_med1_id = self.get_record(db, 'prod_med_1')
        prod_med2_id = self.get_record(db, 'prod_med_2')
        uom_pce_id = self.get_record(db, 'product_uom_unit', module='product')

        order_values = self._get_order_values(db)

        order_id = self.order_obj.create(order_values)

        # Create order lines
        # First line
        line_values = {
            'order_id': order_id,
            'product_id': prod_log1_id,
            'product_uom': uom_pce_id,
            'product_uom_qty': 10.0,
            'type': 'make_to_order',
            'price_unit': 12.24,
        }
        self.order_line_obj.create(line_values)

        # Second line
        line_values.update({
            'product_id': prod_log2_id,
            'product_uom_qty': 20.0,
        })
        self.order_line_obj.create(line_values)

        # Third line
        line_values.update({
            'product_id': prod_med1_id,
            'product_uom_qty': 30.0,
        })
        self.order_line_obj.create(line_values)

        # Fourth line
        line_values.update({
            'product_id': prod_med2_id,
            'product_uom_qty': 40.0,
        })
        self.order_line_obj.create(line_values)

        if self.pr:
            # Validate the Internal Request
            db.exec_workflow('sale.order', 'procurement_validate', order_id)
        else:
            # Validate the Field Order
            db.exec_workflow('sale.order', 'order_validated', order_id)

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
        # Create the field order
        order_id = self.create_order(db)

        # Source all lines on a Purchase Order to ext_supplier_1
        line_ids = self.order_line_obj.search([('order_id', '=', order_id)])
        self.order_line_obj.write(line_ids, {
            'po_cft': 'po',
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
               if line.procurement_id and line.procurement_id.state != 'running':
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

    def _validate_po(self, db, po_ids):
        """
        Check if the PO are in 'draft' state.
        Then, validate them.
        Then, check if all PO are now in 'confirmed' state.

        :param db: Connection to the database
        :param po_ids: List of ID of purchase.order to validate
        :return The list of ID of purchase.order validated
        """
        po_obj = db.get('purchase.order')
        pol_obj = db.get('purchase.order.line')

        # Add an analytic distribution on PO lines that have no
        no_ana_line_ids = pol_obj.search([
            ('order_id', 'in', po_ids),
            ('analytic_distribution_id', '=', False),
        ])
        pol_obj.write(no_ana_line_ids, {
            'analytic_distribution_id': self.create_analytic_distribution(db),
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

    def _get_number_of_ir_valid_lines(self, db, order_id):
        """
        Returns the number of lines in the FO
        :param db: Connection to the database
        :param order_id: ID of the sale.order to get the number of lines
        :return: The number of lines in the FO
        """
        return len(db.get('sale.order.line').search([
            ('order_id', '=', order_id),
            ('state', '!=', 'done'),
        ]))

    def _get_number_of_fo_valid_lines(self, db, order_id):
        """
        Returns the number of lines in the FO
        :param db: Connection to the database
        :param order_id: ID of the sale.order to get the number of lines
        :return: The number of lines in the FO
        """
        return len(db.get('sale.order').read(order_id, ['order_line'])['order_line'])

    def _get_number_of_valid_lines(self, db, order_id):
        if self.pr:
            return self._get_number_of_ir_valid_lines(db, order_id)
        else:
            return self._get_number_of_fo_valid_lines(db, order_id)

    def create_analytic_distribution(self, db):
        """
        Create an analytic distribution
        :param db: Connection on which the distribution must be created
        :return: The ID of distribution
        """
        distrib_obj = db.get('analytic.distribution')
        cc_line_obj = db.get('cost.center.distribution.line')
        fp_line_obj = db.get('funding.pool.distribution.line')

        distrib_id = distrib_obj.create({
            'name': 'Distrib 2',
        })

        cc_line1_id = cc_line_obj.create({
            'name': 'CC Line 1',
            'amount': 0.0,
            'percentage': 75.0,
            'currency_id': self.get_record(db, 'EUR', module='base'),
            'analytic_id': self.get_record(db, 'analytic_cc1'),
            'distribution_id': distrib_id,
            'destination_id': self.get_record(db, 'analytic_account_destination_operation', module='analytic_distribution'),
        })

        cc_line2_id = cc_line_obj.create({
            'name': 'CC Line 2',
            'amount': 0.0,
            'percentage': 25.0,
            'currency_id': self.get_record(db, 'EUR', module='base'),
            'analytic_id': self.get_record(db, 'analytic_cc2'),
            'distribution_id': distrib_id,
            'destination_id': self.get_record(db, 'analytic_account_destination_operation', module='analytic_distribution'),
        })

        fp_line1_id = fp_line_obj.create({
            'name': 'FP Line 1',
            'amount': 0.0,
            'percentage': 75.0,
            'currency_id': self.get_record(db, 'EUR', module='base'),
            'analytic_id': self.get_record(db, 'analytic_cc1'),
            'distribution_id': distrib_id,
            'cost_center_id': self.get_record(db, 'analytic_cc1'),
            'destination_id': self.get_record(db, 'analytic_account_destination_operation', module='analytic_distribution'),
        })

        fp_line2_id = fp_line_obj.create({
            'name': 'FP Line 2',
            'amount': 0.0,
            'percentage': 25.0,
            'currency_id': self.get_record(db, 'EUR', module='base'),
            'analytic_id': self.get_record(db, 'analytic_cc2'),
            'distribution_id': distrib_id,
            'cost_center_id': self.get_record(db, 'analytic_cc1'),
            'destination_id': self.get_record(db, 'analytic_account_destination_operation', module='analytic_distribution'),
        })

        return distrib_id

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
