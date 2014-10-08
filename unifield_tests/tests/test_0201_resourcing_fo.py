#!/usr/bin/env python
# -*- coding: utf8 -*-
from resourcing import ResourcingTest


class ResourcingFOTest(ResourcingTest):

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
        order_id = super(ResourcingFOTest, self).\
            create_order(db)


    def test_010_only_create(self):
        db = self.c1
        order_id = self.create_order(db)


def get_test_class():
    '''Return the class to use for tests'''
    return ResourcingFOTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
