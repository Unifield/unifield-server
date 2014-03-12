#!/usr/bin/env python
# -*- coding: utf8 -*-

from finance import FinanceTest

class InvoiceTest(FinanceTest):
    '''
    Inherits from MasterData in order to permit to reuse the "create_partner()" method.
    '''

    def test_010_invoice(self):
        '''
        I create an invoice with an external supplier and one invoice line.
        '''
        # Search the supplier
        # Create the invoice
        # Add one invoice line
        # Validate the invoice

def get_test_class():
    '''Return the class to use for tests'''
    return InvoiceTest
