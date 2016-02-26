#!/usr/bin/env python
# -*- coding: utf8 -*-

from finance import FinanceTest
from oerplib.error import RPCError
from time import strftime

class InvoiceTest(FinanceTest):

    def test_010_supplier_invoice(self):
        '''
        I create an invoice with an external supplier and one invoice line.
        Then I validate this invoice.
        '''
        # Prepare some values
        db = self.p1
        partner_obj = db.get('res.partner')
        invoice_obj = db.get('account.invoice')
        account_obj = db.get('account.account')
        journal_obj = db.get('account.journal')
        invoice_line_obj = db.get('account.invoice.line')
        analytic_distribution_obj = db.get('analytic.distribution')
        # Search the supplier
        partner_ids = partner_obj.search([('partner_type', '=', 'external'), ('supplier', '=', True)])
        self.assert_(partner_ids != [], "No external supplier partner found!")
        # and its address
        address_ids = db.get('res.partner.address').search([('partner_id', '=', partner_ids[0])])
        self.assert_(address_ids != [], "No address found for this supplier!")
        # Search account
        account_ids = account_obj.search([('code', '=', '401-supplier-test')])
        self.assert_(account_ids != [], "No payable account found! %s")
        # Search journal
        journal_ids = journal_obj.search([('type', '=', 'purchase')])
        self.assert_(journal_ids != [], "No purchase journal found!")
        # Search analytic distribution
        distribution_ids = analytic_distribution_obj.search([('name', '=', 'DISTRIB 1')])
        self.assert_(distribution_ids != [], "No distribution 'DISTRIB 1' found!")
        distribution_id = analytic_distribution_obj.copy(distribution_ids[0], {'name': 'distribution-test'})
        # Create the invoice
        invoice_vals = {
            'type': 'in_invoice',
            'partner_id': partner_ids[0],
            'account_id': account_ids[0],
            'address_contact_id': address_ids[0],
            'address_invoice_id': address_ids[0],
            'company_id': db.user.company_id.id,
            'currency_id': db.user.company_id.currency_id.id,
            'journal_id': journal_ids[0],
            'reference_type': 'none',
            'date': strftime('%Y-%m-%d'),
            'document_date': strftime('%Y-%m-%d'),
            'check_total': 720.0,
        }
        inv_id = invoice_obj.create(invoice_vals)
        self.assert_(inv_id != False, "Invoice creation failed with these values: %s" % invoice_vals)
        # Add one invoice line
        expense_account_ids = account_obj.search([('code', '=', '6101-expense-test')])
        self.assert_(expense_account_ids != [], "No expense account found!")
        invoice_line_vals = {
            'invoice_id': inv_id,
            'name': 'Some products',
            'account_id': expense_account_ids[0],
            'price_unit': 120.0,
            'quantity': 6.0,
            'analytic_distribution_id': distribution_id,
        }
        invl_id = invoice_line_obj.create(invoice_line_vals)
        self.assert_(invl_id != False, "Invoice line creation failed with given values: %s" % invoice_line_vals)
        # Validate the invoice
        try:
            res = db.exec_workflow('account.invoice', 'invoice_open', inv_id)
        except RPCError, e:
            raise Exception("\n### OpenERP error ###\n%s\n\n%s" % (e.message, e.oerp_traceback))
        self.assert_(res != False, "Invoice validation failed!")
        # Check that the invoice state is "open"
        invoice = invoice_obj.browse(inv_id)
        self.assert_(invoice.state == 'open', "Invoice %s is not open but in %s state!" % (invoice.name or '', invoice.state or ''))
        # Check that invoice have a move line attached to the invoice line
        move_lines = db.search('account.move.line', [('invoice_line_id', '=', invl_id)])
        self.assertNotEqual(move_lines, [], "No move lines generated!")
        self.assertEqual(len(move_lines), 1, "Expect 1 move line. Found: %s" % len(move_lines))
        # Check that analytic lines have been generated for given move lines
        analytic_lines = db.get('account.analytic.line').search([('move_id', 'in', move_lines)])
        self.assertNotEqual(analytic_lines, [], "No analytic lines generated!")

    def test_020_purchase_order_invoice(self):
        '''
        Create a regular purchase order with an external supplier.
        First Validate the purchase order.
        Then process the stock.picking.
        Finally check that invoice was generated.
        Then validate it.
        '''
        # TODO: CREATE THIS TEST IN ORDER TO CHECK INVOICE CREATION AFTER A PO CREATION + STOCK process validation
        pass

def get_test_class():
    '''Return the class to use for tests'''
    return InvoiceTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
