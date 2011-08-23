# -*- coding: utf-8 -*-
'''
Created on 22 août 2011

@author: openerp
'''
from common import *
from config import *

class TestMSFMessage(TestMSF):  
    def create_po(self, host, port, db_name, supplier_name, ):
        partner_id = self.get_record_id(host, port, db_name, 'res.partner', supplier_name)
        address_id = self.get_record_id(host, port, db_name, 'res.partner.address', supplier_name)
        self.create_record(host, port, db_name, 'purchase.order', {'partner_id' : partner_id, 
                                                               'pricelist_id' : 1, 
                                                               'partner_address_id' :  address_id,
                                                               'location_id' : 1,
                                                               'state' : 'approved'})
        
        
class TestSoToPo(TestMSFMessage):
    def runTest(self):
        self.create_record(client_host, client_port, 'msf_c1', 'res.partner', {'name' : 'msf_c2', 'address' : [(0,0, {'name' : 'msf_c2'})]})
        self.create_po(client_host, client_port, 'msf_c1', 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c1')
        self.synchronize(client_host, client_port, 'msf_c2')
        
        
if __name__ == '__main__':
    test = unittest.TestSuite()
    test.addTest(TestSoToPo())
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test)                            