#!/usr/bin/env python
# -*- coding: utf8 -*-

from unifield_test import UnifieldTest

class RemoteWarehouseTest(UnifieldTest):

  def setUp(self):
        if not self.is_remote_warehouse:
            raise UserWarning("Remote Warehouse deactivated. This test will be not achieve.")

def get_test_class():
    '''Return the class to use for tests'''
    return RemoteWarehouseTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
