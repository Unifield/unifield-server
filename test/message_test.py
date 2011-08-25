# -*- coding: utf-8 -*-


'''
Created on 22 août 2011

@author: openerp
'''
from common import *
from config import *
import uuid


            
class TestPoToSo(TestMSFMessage):
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_c1', 'product.product', 
                           {'name' : 'A10'})
        self.create_record(client_host, client_port, 'msf_c1', 'res.partner', 
                           {'name' : 'msf_c1', 
                            'address' : [(0,0, {'name' : 'msf_c1'})]  
                            })
        self.create_record(client_host, client_port, 'msf_c2', 'res.partner', 
                           {'name' : 'msf_c2', 
                            'address' : [(0,0, {'name' : 'msf_c2'})]  
                            })
        self.synchronize(client_host, client_port, 'msf_c1')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c1')
        
    """
        Use case 6
    """
    def runTest(self):
        po_name = 'PO%s' % uuid.uuid1().hex
        self.create_po(client_host, client_port, 'msf_c1', 'msf_c2', po_name, 'A10')
        self.synchronize(client_host, client_port, 'msf_c1')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.check_model_data_like(client_host, client_port, 'msf_c2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_c1.' + po_name })
        
    

class TestPoToSo2(TestMSFMessage):
    
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'A11'})
        self.create_record(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'A12'})
        self.create_record(client_host, client_port, 'msf_p2', 'res.partner', 
                           {
                            'name' : 'msf_p2', 
                            'address' : [(0,0, {'name' : 'msf_p2'})]  
                            })
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')

 
    def runTest(self):
        po2_name = 'PO%s' % uuid.uuid1().hex
        po3_name = 'PO%s' % uuid.uuid1().hex
        self.create_po(client_host, client_port, 'msf_p2', 'msf_c2', po2_name, 'A11')
        self.create_po(client_host, client_port, 'msf_p2', 'msf_c2', po3_name, 'A12')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.check_model_data_like(client_host, client_port, 'msf_c2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p2.' + po2_name })
        self.check_model_data_like(client_host, client_port, 'msf_c2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p2.' + po3_name })

        
class TestExternalSupplierPO(TestMSFMessage):
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_c1', 'product.product', {'name' : 'A13'})
        self.create_record(client_host, client_port, 'msf_p1', 'product.product', {'name' : 'A14'})
        self.create_record(client_host, client_port, 'msf_c1', 'res.partner', 
                           {
                            'name' : 'external_supplier1', 
                            'address' : [(0,0, {'name' : 'external_supplier1'})]  
                            })
        self.create_record(client_host, client_port, 'msf_p1', 'res.partner', 
                           {
                            'name' : 'external_supplier2', 
                            'address' : [(0,0, {'name' : 'external_supplier2'})]  
                            })
    def runTest(self):
        po4_name = 'PO%s' % uuid.uuid1().hex
        po5_name = 'PO%s' % uuid.uuid1().hex
        self.create_po(client_host, client_port, 'msf_c1', 'external_supplier1', po4_name, 'A13')
        self.create_po(client_host, client_port, 'msf_p1', 'external_supplier2', po5_name, 'A14')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_c1')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c3')
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_c1.' + po4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p1.' + po5_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_c1.' + po4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p1.' + po5_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p3', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_c1.' + po4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p3', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p1.' + po5_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_c1', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_c1.' + po4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_c1', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p1.' + po5_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_c2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_c1.' + po4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_c2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p1.' + po5_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_c3', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_c1.' + po4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_c3', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p1.' + po5_name }, False)
    
class TestExternalSupplierSO(TestMSFMessage):
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_c1', 'res.partner', 
                           {
                            'name' : 'external_supplier3', 
                            'address' : [(0,0, {'name' : 'external_supplier3'})]  
                            })
    def runTest(self):
        so4_name = 'SO%s' % uuid.uuid1().hex
        self.create_so(client_host, client_port, 'msf_c1', 'external_supplier3', so4_name, 'A11')
        self.synchronize(client_host, client_port, 'msf_c1')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c3')
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'purchase.order', {'name' : 'SO', 'partner_ref' : 'msf_p1.' + so4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'purchase.order', {'name' : 'SO', 'partner_ref' : 'msf_p1.' + so4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'purchase.order', {'name' : 'SO', 'partner_ref' : 'msf_p1.' + so4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'purchase.order', {'name' : 'SO', 'partner_ref' : 'msf_p1.' + so4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'purchase.order', {'name' : 'SO', 'partner_ref' : 'msf_p1.' + so4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'purchase.order', {'name' : 'SO', 'partner_ref' : 'msf_p1.' + so4_name }, False)
        self.check_model_data_like(client_host, client_port, 'msf_p1', 'purchase.order', {'name' : 'SO', 'partner_ref' : 'msf_p1.' + so4_name }, False)
        
    
class TestSoToPo(TestMSFMessage):
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_c2', 'product.product', {'name' : 'A11'})
        self.create_record(client_host, client_port, 'msf_p3', 'res.partner', 
                           {
                            'name' : 'msf_p3', 
                            'address' : [(0,0, {'name' : 'msf_p3'})]  
                            })
        self.synchronize(client_host, client_port, 'msf_p3')
        self.synchronize(client_host, client_port, 'msf_c2')
    def runTest(self):
        so5_name = 'SO%s' % uuid.uuid1().hex
        self.create_so(client_host, client_port, 'msf_c2', 'msf_p3', so5_name, 'A11')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.check_model_data_like(client_host, client_port, 'msf_p3', 'purchase.order', {'name' : 'PO', 'partner_ref' : 'msf_c2.' + so5_name })
   
class TestConfirmPo(TestMSFMessage):
    def setUp(self):
        self.po2_name = 'PO%s' % uuid.uuid1().hex
        self.create_record(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'B309'})
        self.create_po(client_host, client_port, 'msf_p2', 'msf_c2', self.po2_name, 'B309')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
    
    def runTest(self):
        self.check_model_data(client_host, client_port, 'msf_p2', 'purchase.order', {'name' : self.po2_name, 'state' : 'confirmed'  })
        self.confirm_so(client_host, client_port, 'msf_c2', 'msf_p2.' + self.po2_name)
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.check_model_data(client_host, client_port, 'msf_p2', 'purchase.order', {'name' : self.po2_name, 'state' : 'approved'  })


class ShippementConfirmation(TestMSFMessage):
    def setUp(self):
        self.po2_name = 'PO%s' % uuid.uuid1().hex
        self.create_record(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'C4'})
        self.create_po(client_host, client_port, 'msf_p2', 'msf_c2', self.po2_name, 'C4')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.confirm_so(client_host, client_port, 'msf_c2', 'msf_p2.' + self.po2_name)
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.check_model_data(client_host, client_port, 'msf_p2', 'purchase.order', {'name' : self.po2_name, 'state' : 'approved'  })

    def runTest(self):
        self.confirm_shippements(client_host, client_port, 'msf_c2', 'msf_p2.' + self.po2_name)
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.check_model_data(client_host, client_port, 'msf_p2', 'purchase.order', {'name' : self.po2_name, 'sended_by_supplier' : True  })
        self.confirm_incoming_shippements(client_host, client_port, 'msf_p2', self.po2_name)
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.check_model_data_like(client_host, client_port, 'msf_c2', 'sale.order', {'name' : 'SO', 'client_order_ref' : 'msf_p2.' + self.po2_name, 'received' : True  })
        #confirm shippement
        #check PO2 state
    
if __name__ == '__main__':
    test = unittest.TestSuite()
    test.addTest(TestPoToSo())
    test.addTest(TestPoToSo2())
    test.addTest(TestExternalSupplierPO())
    test.addTest(TestExternalSupplierSO())
    test.addTest(TestSoToPo())
    #Database has to be configured to execute this test
    test.addTest(TestConfirmPo())
    test.addTest(ShippementConfirmation())
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test)                            