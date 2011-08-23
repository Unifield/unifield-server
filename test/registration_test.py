# -*- coding: utf-8 -*-
# Author : OpenERP
import unittest
import rpc

from config import *
from common import *


class TestConnection(TestMSF): 
    def runTest(self):
        """
            Use case : First of all the client has to setup the connection to the sync server,
            if the uid is not null then the connection is effective
        """
        self.single_test_connection(client_host, client_port, 'msf_c1')       
  
class TestActivation(TestMSF):        
    def runTest(self):
        """
            Use Case : the entity msf_c1 has been created server side, with csv, but
            still need to get the information, we check that the parent is the right one.
        """
        self.single_test_connection(client_host, client_port, 'msf_c1')
        self.single_activation_test(client_host, client_port, 'msf_c1', 'root') 
  
class TestRegistration(TestMSF):
    def runTest(self):
        """
            Use Case : The entity register himself to the server and wait for activation from the parent
            Test if the entity exist server side and is pending
        """
        self.single_test_connection(client_host, client_port, 'msf_p3')
        self.single_register_test(client_host, client_port, 'msf_p3', 'msf_c2', ['Mission 2', 'International', 'Section 1'])

class TestValidationAfterRegistration(TestMSF):
    """
     UCG1 Part 1 : P3 register with c2 as parent, c2 validate check that p3 is well registered
    """
    def runTest(self):
        self.single_test_connection(client_host, client_port, 'msf_c2')
        self.single_activation_test(client_host, client_port, 'msf_c2', 'root') 
        
        self.single_test_connection(client_host, client_port, 'msf_p3')
        self.single_register_test(client_host, client_port, 'msf_p3', 'msf_c2', ['Mission 2', 'International', 'Section 1'])
        self.single_activate_by_parent(client_host, client_port, 'msf_c2', 'msf_p3')

class MissingValidation(TestMSF):

    def runTest(self):
        self.single_test_connection(client_host, client_port, 'msf_c3')
        self.single_activation_test(client_host, client_port, 'msf_c3', 'root') 
        
        self.single_test_connection(client_host, client_port, 'msf_p1')
        self.single_activation_test(client_host, client_port, 'msf_p1', 'msf_c1')
        
        self.single_test_connection(client_host, client_port, 'msf_p2')
        self.single_activation_test(client_host, client_port, 'msf_p2', 'msf_c2')  
    
        
if __name__ == '__main__':
    test = unittest.TestSuite()
    test.addTest(TestConnection())
    test.addTest(TestActivation())
    test.addTest(TestRegistration())
    test.addTest(TestValidationAfterRegistration())
    test.addTest(MissingValidation())
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test)