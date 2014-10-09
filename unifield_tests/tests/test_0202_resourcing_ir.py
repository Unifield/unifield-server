#!/usr/bin/env python
# -*- coding: utf8 -*-
from resourcing import ResourcingTest

import time


class ResourcingIRTest(ResourcingTest):

    def _get_order_values(self, db, values=None):
        """
        Returns specific values for an Internal Request

        :param db: Cursor to the database
        :param values: Default values to update

        :return The values of the internal request
        :rtype dict
        """
        if values is None:
            values = {}

        # Get some objects
        data_obj = db.get('ir.model.data')

        values = super(ResourcingIRTest, self).\
            _get_order_values(db, values)

        location_id = data_obj.get_object_reference(
            'stock',
            'stock_location_stock',
        )[1]

        values.update({
            'procurement_request': True,
            'location_requestor_id': location_id,
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
        # Prepare data
        order_id = super(ResourcingIRTest, self).\
            create_order(db)

        # Validate the Internal Request
        db.exec_workflow('sale.order', 'procurement_validate', order_id)

        return order_id

#    def test_010_all_on_po_cancel_po(self):
#        """
#        Create an internal request and source all lines on one PO. Then,
#        cancel the PO.
#        """
#        db = self.c1
#
#        order_id, order_line_ids, po_ids, po_line_ids = self.\
#            order_source_all_one_po(db)

def get_test_class():
    '''Return the class to use for tests'''
    return ResourcingIRTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
