# -*- coding: utf-8 -*-
# Author : OpenERP
from common import *
from config import *
import uuid

class TestMSFFinancial(TestMSFMessage):
    
    def create_data_ucf1(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.create_data_ucf1()
        self.assertTrue(res)
    
    def modify_data_ucf1(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.modify_data_ucf1()
        self.assertTrue(res)

    def check_final_data_ucf1(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.check_final_data_ucf1()
        self.assertTrue(res)
        
    def create_data_ucf2(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.create_data_ucf2()
        self.assertTrue(res)
        
    def create_cash_statement_ufc2(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.create_cash_statement_ufc2()
        self.assertTrue(res)
        
    def reconcile_ucf2(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.reconcile_ucf2()
        self.assertTrue(res)
        
    def init_data_ucf3(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.init_data_ucf3()
        self.assertTrue(res)
        
    def register_invoice_payment_ucf3(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.register_invoice_payment_ucf3()
        self.assertTrue(res)

    def check_final_data_ucf3(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.check_final_data_ucf3()
        self.assertTrue(res)

    def create_data_ucf4(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.create_data_ucf4()
        self.assertTrue(res)
        
    def change_distribution_ucf4(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.change_distribution_ucf4()
        self.assertTrue(res)
        
class TestUCF1(TestMSFFinancial):
    
    def runTest(self):
        self.create_data_ucf1(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.modify_data_ucf1(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c2')        
        self.synchronize(client_host, client_port, 'msf_p2')
        self.check_final_data_ucf1(client_host, client_port, 'msf_p2')
     
class TestUCF2(TestMSFFinancial): 
    def runTest(self):
        self.create_data_ucf2(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.create_cash_statement_ufc2(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.reconcile_ucf2(client_host, client_port, 'msf_c2')
        self.reconcile_ucf2(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
        #Conflict detected should appear in console output
        
class TestUCF3(TestMSFFinancial):
    """Short description:
    P1 creates a local supplier S2 and registers an expense with this partner in P1 bank register.
    Then synchronisation takes place.

    - P1 creates supplier S2
    - P1 creates and validates a supplier invoice with S2 
    - P1 registers invoice payment in “P1 Bank register in USD / 001”
    - When synchronisation takes place, the new partner S2 must be created first
      in C1 database so that the supplier invoice created can be replicated in
      turn.
    """

    def runTest(self):
        self.init_data_ucf3(client_host, client_port, 'msf_p1')
        self.register_invoice_payment_ucf3(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_c1')
        self.check_final_data_ucf3(client_host, client_port, 'msf_c1')

class TestUCF4(TestMSFFinancial):
    def runTest(self):
        #
        self.create_data_ucf4(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.change_distribution_ucf4(client_host, client_port, "msf_p2")
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
        #Check first Analytic account has items with 2000 in c2 also 

if __name__ == '__main__':
    test = unittest.TestSuite()
    test.addTest(TestUCF1())
    test.addTest(TestUCF2())
    test.addTest(TestUCF3())
    test.addTest(TestUCF4())
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test)
