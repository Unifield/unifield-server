#!/usr/bin/env python
# -*- coding: utf8 -*-
from unifield_test import UnifieldTest

class AccountTest(UnifieldTest):

    def test_010_coa(self):
        '''Check Chart of Account length'''
        ids = self.p1.get('account.account').search([])
        self.assert_(len(ids) == 357, "Chart of Account length: %s" % len(ids))

def get_test_class():
    '''Return the class to use for tests'''
    return AccountTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
