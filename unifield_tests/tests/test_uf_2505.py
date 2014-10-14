#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = 'qt'

from resourcing import ResourcingTest

import time


class UF2505ResourcingTest(ResourcingTest):

    def test_uf_2505(self):
        """
        Create two field ordes and source them on the same PO. Then,
        validate and confirm the PO.
        """
        # if not isinstance(self, (UF2505ResourcingFOTest, UF2505ResourcingIRTest)):
        #     return
        db = self.used_db

        # Create and source the first FO
        f_order_id, f_order_line_ids, f_po_ids, f_po_line_ids = self.order_source_all_one_po(db)

        # Check if the number of created PO is good
        self.assert_(len(f_po_ids) == 1, msg="""
The number of generated POs is %s - Should be 1.""" % len(f_po_ids))

        # Create and source the second FO
        s_order_id, s_order_line_ids, s_po_ids, s_po_line_ids = self.order_source_all_one_po(db)

        # Check if the number of created PO is good
        self.assert_(len(s_po_ids) == 1, msg="""
The number of generated POs is %s - Should be 1.""" % len(s_po_ids))

        # Check the two orders have been sourced on the same PO
        self.assertEquals(f_po_ids, s_po_ids, msg="""
The two orders have not been sourced on the same PO :: %s - %s""" % (s_po_ids, f_po_ids))

        self._validate_po(db, s_po_ids)

        # Confirm POs
        self.po_obj.write(s_po_ids, {
            'delivery_confirmed_date': time.strftime('%Y-%m-%d'),
        })
        try:
            self.po_obj.confirm_button(s_po_ids)
        except Exception as e:
            self.assert_(False, str(e))

        # Last check
        for po_id in s_po_ids:
            po_state = self.po_obj.read(po_id, ['state'])['state']
            self.assert_(po_state == 'approved', msg="""
The state of the generated PO is %s - Should be 'approved'""" % po_state)

        ## End of test
        return True


class UF2505FOResourcingTest(UF2505ResourcingTest):

    def setUp(self):
        self.pr = False
        super(UF2505FOResourcingTest, self).setUp()


class UF2505IRResourcingTest(UF2505ResourcingTest):

    def setUp(self):
        self.pr = True
        super(UF2505IRResourcingTest, self).setUp()



def get_test_suite():
    '''Return the class to use for tests'''
    return UF2505FOResourcingTest, UF2505IRResourcingTest