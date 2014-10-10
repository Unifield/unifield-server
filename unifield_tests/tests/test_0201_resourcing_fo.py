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
        partner_id = self.get_record(db, 'ext_customer_1')
        p_addr_id = self.get_record(db, 'ext_customer_1_addr')
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
        distrib_id = self.get_record(db, 'distrib_1')
        order_obj.write(order_id, {'analytic_distribution_id': distrib_id})

        # Validate the Field Order
        db.exec_workflow('sale.order', 'order_validated', order_id)

        return order_id

    def _get_number_of_valid_lines(self, db, order_id):
        """
        Returns the number of lines in the FO
        :param db: Connection to the database
        :param order_id: ID of the sale.order to get the number of lines
        :return: The number of lines in the FO
        """
        return len(db.get('sale.order').read(order_id, ['order_line'])['order_line'])


def get_test_class():
    '''Return the class to use for tests'''
    return ResourcingFOTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
