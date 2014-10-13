#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from unifield_test import UnifieldTest
from resourcing import ResourcingTest

import time


class UF2505ResourcingTest(UnifieldTest):

    def uf_2505(self, cls_test):
        """
        Create two field ordes and source them on the same PO. Then,
        validate and confirm the PO.
        """
        # if not isinstance(self, (UF2505ResourcingFOTest, UF2505ResourcingIRTest)):
        #     return
        db = self.c1

        # Prepare object
        po_obj = db.get('purchase.order')

        # Create and source the first FO
        f_order_id, f_order_line_ids, f_po_ids, f_po_line_ids = cls_test.\
            order_source_all_one_po(db)

        # Check if the number of created PO is good
        self.assert_(len(f_po_ids) == 1, msg="""
The number of generated POs is %s - Should be 1.""" % len(f_po_ids))

        # Create and source the second FO
        s_order_id, s_order_line_ids, s_po_ids, s_po_line_ids = cls_test.\
            order_source_all_one_po(db)

        # Check if the number of created PO is good
        self.assert_(len(s_po_ids) == 1, msg="""
The number of generated POs is %s - Should be 1.""" % len(s_po_ids))

        # Check the two orders have been sourced on the same PO
        self.assertEquals(f_po_ids, s_po_ids, msg="""
The two orders have not been sourced on the same PO :: %s - %s""" % (s_po_ids, f_po_ids))

        cls_test._validate_po(db, s_po_ids)

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

    def test_fo_uf_2505(self):
        cls_test = ResourcingTest(pr=False)
        return self.uf_2505(cls_test)

    def test_ir_uf_2505(self):
        cls_test = ResourcingTest(pr=True)
        return self.uf_2505(cls_test)



def get_test_class():
    '''Return the class to use for tests'''
    return UF2505ResourcingTest