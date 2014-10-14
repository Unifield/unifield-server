#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest

import time


class UF2490OnePO(ResourcingTest):

    def create_po_from_scratch(self):
        """
        Create a PO from scratch, then cancel it.
        :return: The ID of the new purchase order
        """
        db = self.used_db

        # Create PO
        partner_id = self.get_record(db, 'ext_supplier_1')
        po_values = {
            'partner_id': partner_id,
            'partner_address_id': self.get_record(db, 'ext_supplier_1_addr'),
            'location_id': self.get_record(db, 'stock_location_stock', module='stock'),
        }
        po_values.update(
            self.po_obj.onchange_partner_id(None, partner_id, time.strftime('%Y-%m-%d'), None, None).get('value', {})
        )
        po_id = self.po_obj.create(po_values)

        return po_id

    def create_po_line(self, order_id):
        """
        Create a purchase order line
        :param order_id: The ID of the order where the line will be added
        :return: The ID of the new purchase order line
        """
        db = self.used_db

        po_brw = self.po_obj.browse(order_id)

        product_id = self.get_record(db, 'prod_log_1')
        uom_id = self.get_record(db, 'product_uom_unit', module='product')
        pol_values = {
            'product_id': product_id,
            'product_uom': uom_id,
            'product_qty': 10.00,
            'price_unit': 1.00,
            'order_id': order_id,
            'date_planned': False,
        }

        pol_values.update(
            self.pol_obj.product_id_on_change(None, po_brw.pricelist_id.id, product_id, 10.00, uom_id,
                                              po_brw.partner_id.id,
                                              po_brw.date_order.strftime('%Y-%m-%d'), po_brw.fiscal_position, False,
                                              'name',
                                              1.00, None, po_brw.state, 1.00, None, None, None).get('value', {})
        )
        self.pol_obj.create(pol_values)

    def cancel_po(self, order_id):
        """
        Cancel the PO
        :param order_id: The ID of the PO to cancel
        :return: ID of the canceled PO
        """
        db = self.used_db

        self.po_obj.purchase_cancel(order_id)

        # Check state of the PO
        po_state = self.po_obj.read(order_id, ['state'])['state']
        self.assert_(
            po_state == 'cancel',
            "The state of the PO is '%s' - Should be 'cancel'" % po_state,
        )

    def check_order_state(self, mode='sourced'):
        """
        Check the state of the order (Implemented in children classes)
        :param mode: 'sourced' or 'closed'
        :return:
        """
        raise NotImplemented

    def create_order_and_source(self):
        """
        Create a FO/IR with 4 lines, source it to a Po
        :return:
        """
        fo_id, fo_line_ids, po_ids, pol_ids = self.order_source_all_one_po(self.used_db)
        self.order_id = fo_id
        self.po_id = po_ids[0]

    def create_order_cancel_po(self):
        """
        Create a FO/IR with 4 lines, source it to a PO
        Then cancel the PO
        :return: Result of the PO cancelation wizard
        """
        db = self.used_db

        # Prepare object
        wiz_model = 'purchase.order.cancel.wizard'
        wiz_obj = db.get(wiz_model)

        # Create the FO/IR and source it
        self.create_order_and_source()

        c_res = self.po_obj.purchase_cancel(self.po_id)

        self.assert_(
            c_res.get('res_id', False),
            "No wizard displayed when the PO is canceled",
        )
        self.assert_(
            c_res.get('res_model', False) == wiz_model,
            "The wizard displayed on PO cancelation is not good :: '%s' - Should be '%s'" %
            (c_res.get('res_model'), wiz_model)
        )

        # Validate cancellation
        w_res = wiz_obj.cancel_po(c_res.get('res_id'))

        po_state = self.po_obj.read(self.po_id, ['state'])['state']
        # Check the state of PO is not changed
        self.assert_(
            po_state == 'cancel',
            u"The state of the PO is '{0:s}' - Should be 'cancel'".format(po_state)
        )

        # Check if the wizard to choose what must be done on the FO/IR is well displayed
        self.assert_(
            w_res.get('res_id', False),
            "The wizard to choose what must be done on the FO/IR is not well displayed."
        )
        self.assert_(
            w_res.get('res_model', False) == 'sale.order.cancelation.wizard',
            "The wizard to choose what must be done on the FO/IR is displayed, but it's not the good wizard."
        )

        self.check_order_state(mode='sourced')

        return w_res

    # #########
    #
    #  Begin of tests
    #
    ##########
    def test_cancel_empty_po_from_scratch(self):
        """
        Create an empty PO and cancel it
        :return:
        """
        # Create PO
        po_id = self.create_po_from_scratch()

        # Cancel PO
        self.cancel_po(po_id)

    def test_cancel_non_empty_po_from_scratch(self):
        """
        Create a PO from scratch, add a line on the PO
        then, cancel it.
        """
        # Create PO
        po_id = self.create_po_from_scratch()

        # Create PO line
        self.create_po_line(po_id)

        # Cancel PO
        self.cancel_po(po_id)

    def test_cancel_validated_po_from_scracth(self):
        """
        Create a PO from scratch, add a line on the PO,
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
        db.exec_workflow('purchase.order', 'purchase_confirm', po_id)

        # Cancel the PO
        self.cancel_po(po_id)

    def test_create_order_cancel_po_leave_order(self):
        """
        Create a FO/IR, source it on PO
        Then cancel PO. When the system asks user
        what should be done on FO/IR, choose leave it
        :return:
        """
        db = self.used_db

        # Prepare object
        w_line_obj = db.get('sale.order.leave.close')
        wiz_obj = db.get('sale.order.cancelation.wizard')

        w_res = self.create_order_cancel_po()

        w_line_ids = w_line_obj.search([
            ('wizard_id', '=', w_res.get('res_id')),
            ('order_id', '=', self.order_id),
        ])

        self.assert_(
            len(w_line_ids) == 1,
            "The number of lines in the wizard is %s - Should be 1" % len(w_line_ids),
        )

        # Choose leave it
        w_line_obj.write(w_line_ids, {'action': 'leave'})

        wiz_obj.close_fo(w_res.get('res_id'))

        self.check_order_state(mode='closed')

    def test_create_order_cancel_po_close_order(self):
        """
        Create an FO/IR, source it on PO
        Then cancel PO. When the system asks user
        what should be done on FO/IR, choose close it
        :return:
        """
        db = self.used_db

        # Prepare object
        w_line_obj = db.get('sale.order.leave.close')
        wiz_obj = db.get('sale.order.cancelation.wizard')

        w_res = self.create_order_cancel_po()

        w_line_ids = w_line_obj.search([
            ('wizard_id', '=', w_res.get('res_id')),
            ('order_id', '=', self.order_id),
        ])

        self.assert_(
            len(w_line_ids) == 1,
            "The number of lines in the wizard is %s - Should be 1" % len(w_line_ids),
        )

        # Choose leave it
        w_line_obj.write(w_line_ids, {'action': 'close'})

        wiz_obj.close_fo(w_res.get('res_id'))

        self.check_order_state(mode='closed')

    def test_create_order_cancel_line(self):
        """
        Create a FO/IR with 4 lines. Source all lines on
        a PO, then cancel line.
        :return:
        """
        db = self.used_db

        self.create_order_and_source()

        line_ids = self.pol_obj.search([('order_id', '=', self.po_id)])

        #for x in xrange(0, len(line_ids)-1):
            #if



        #res = self.pol_obj.ask_unlink(line_brw.id)

        self.assert_(
            res.get('res_id', False),
            "There is no wizard displayed when cancel a PO line that sources a FO/IR line",
        )
        self.assert_(
            res.get('res_model', False) == 'urchase.order.line.unlink.wizard',
            "There is a displayed wizard but it's not the good wizard",
        )


class UF2490FOOnePO(UF2490OnePO):
    def setUp(self):
        self.pr = False
        super(UF2490FOOnePO, self).setUp()

    def check_order_state(self, mode='sourced'):
        """
        Check the state of the order
        :param mode: 'sourced' or 'clostest_create_ired'
        :return:
        """
        if mode == 'sourced':
            order_to_check = 'sourced'
        else:
            order_to_check = 'done'

        order_state = self.order_obj.read(self.order_id, ['state'])['state']
        self.assert_(
            order_state == order_to_check,
            "The FO state is '%s' - Should be '%s'" % (order_state, order_to_check),
        )


class UF2490IROnePO(UF2490OnePO):
    def setUp(self):
        self.pr = True
        super(UF2490IROnePO, self).setUp()

    def check_order_state(self, mode='sourced'):
        """
        Check the state of the order
        :param mode: 'sourced' or 'closed'
        :return:
        """
        if mode == 'sourced':
            order_to_check = 'sourced'
        else:
            order_to_check = 'done'

        order_state = self.order_obj.read(self.order_id, ['state'])['state']
        self.assert_(
            order_state == order_to_check,
            "The IR state is '%s' - Should be '%s'" % (order_state, order_to_check),
        )


def get_test_suite():
    '''Return the class to use for tests'''
    return UF2490FOOnePO, UF2490IROnePO