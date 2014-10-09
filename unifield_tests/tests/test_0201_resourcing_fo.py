#!/usr/bin/env python
# -*- coding: utf8 -*-
from resourcing import ResourcingTest

import time


class ResourcingFOTest(ResourcingTest):

    def _get_order_values(self, db, values=None):
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

        # Prepare some objects
        order_obj = db.get('sale.order')

        # Prepare values for the field order
        partner_id = self.get_test_obj(db, 'ext_customer_1')
        p_addr_id = self.get_test_obj(db, 'ext_customer_1_addr')
        order_type = 'regular'

        values = super(ResourcingFOTest, self).\
            _get_order_values(db, values)

        change_vals = order_obj.\
            onchange_partner_id(None, partner_id, order_type).get('value', {})
        values.update(change_vals)

        values.update({
            'order_type': order_type,
            'procurement_request': False,
            'partner_id': partner_id,
            'ready_to_ship_date': time.strftime('%Y-%m-%d'),
        })

        return values


    def create_order(self, db):
        """
        Create a field order (sale.order) with 4 lines:
        - 2 lines with LOG products:
            - 1 line with 10 PCE
            - 1 line with 20 PCE
        - 2 lines with MED products:
            - 1 line with 30 PCE
            - 1 line with 40 PCE
        """
        # Prepare object
        order_obj = db.get('sale.order')

        # Prepare data
        order_id = super(ResourcingFOTest, self).\
            create_order(db)

        # Add an analytic distribution
        distrib_id = self.get_test_obj(db, 'distrib_1')
        order_obj.write(order_id, {'analytic_distribution_id': distrib_id})

        # Validate the Field Order
        db.exec_workflow('sale.order', 'order_validated', order_id)

        return order_id

    def test_uf_2505(self):
        """
        Create two field ordes and source them on the same PO. Then,
        validate and confirm the PO.
        """
        db = self.c1

        # Prepare object
        po_obj = db.get('purchase.order')

        # Create and source the first FO
        f_order_id, f_order_line_ids, f_po_ids, f_po_line_ids = self.\
            order_source_all_one_po(db)

        # Check if the number of created PO is good
        self.assert_(len(f_po_ids) == 1, msg="""
The number of generated POs is %s - Should be 1.""" % len(f_po_ids))

        # Create and source the second FO
        s_order_id, s_order_line_ids, s_po_ids, s_po_line_ids = self.\
            order_source_all_one_po(db)

        # Check if the number of created PO is good
        self.assert_(len(s_po_ids) == 1, msg="""
The number of generated POs is %s - Should be 1.""" % len(s_po_ids))

        # Check the two orders have been sourced on the same PO
        self.assertEquals(f_po_ids, s_po_ids, msg="""
The two orders have not been sourced on the same PO :: %s - %s""" % (s_po_ids, f_po_ids))

        self._validate_po(db, s_po_ids)

        # Confirm POs
        po_obj.write(s_po_ids, {
            'delivery_confirmed_date': time.strftime('%Y-%m-%d'),
        })
        try:
            po_obj.confirm_button(s_po_ids)
        except Exception as e:
            self.assert_(False, str(e))

        # Last check
        for po_id in s_po_ids:
            po_state = po_obj.read(po_id, ['state'])['state']
            self.assert_(po_state == 'approved', msg="""
The state of the generated PO is %s - Should be 'approved'""" % po_state)

        ## End of test
        return True


#    def test_010_all_on_po_cancel_po(self):
#        """
#        Create a field order and source all lines on one PO. Then,
#        cancel the PO.
#        """
#        db = self.c1
#
#        # Prepare object
#        po_obj = db.get('purchase.order')
#
#        order_id, order_line_ids, po_ids, po_line_ids = self.\
#            order_source_all_one_po(db)
#
#        # Check if the number of created PO is good
#        self.assert_(len(po_ids) == 1, msg="""
#The number of generated POs is %s - Should be 1.""" % len(po_ids))
#
#        # Check if the PO is draft
#        for po_id in po_ids:
#            po_state = po_obj.browse(po_id).state
#            self.assert_(po_state == 'draft', msg="""
#The state of the generated PO is %s - Should be 'draft'""" % po_state)


def get_test_class():
    '''Return the class to use for tests'''
    return ResourcingFOTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
