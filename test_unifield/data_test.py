# -*- coding: utf-8 -*-
# Author : OpenERP
import unittest
import rpc

from config import *
from common import *



"""
    Test on data synchronization,
    registration test has to 
    
"""

class TestDataSyncBase(TestMSF):
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_c2', 'res.partner', {'name' : 'msf_test1'})
        self.create_record(client_host, client_port, 'msf_p3', 'res.partner', {'name' : 'msf_test2'})
    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c2', 'res.partner', 'msf_test1')
        self.delete_record(client_host, client_port, 'msf_c2', 'res.partner', 'msf_test2')
        self.delete_record(client_host, client_port, 'msf_p3', 'res.partner', 'msf_test1')
        self.delete_record(client_host, client_port, 'msf_p3', 'res.partner', 'msf_test2')
        
    
    """
     UCG1 Part 2 : P3 and c2 synchronize partner that start with msf
     Check that p1 and p2 has the same partner
    """
    def runTest(self):
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.check_model_data(client_host, client_port, 'msf_c2', 'res.partner', {'name' : 'msf_test2'} )
        self.check_model_data(client_host, client_port, 'msf_p3', 'res.partner', {'name' : 'msf_test1'} )

class TestNoRuleChange(TestMSF):
    """
     UCG2 Part 1 : 
    """
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_c2', 'res.partner', {'name' : 'msf_common'})

    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c2', 'res.partner', 'msf_common')
        self.delete_record(client_host, client_port, 'msf_p1', 'res.partner', 'msf_common')
        
    def runTest(self):
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.check_model_data(client_host, client_port, 'msf_p1', 'res.partner', {'name' : 'msf_common'} )

class TestRuleChange(TestMSF):
    """
     UCG2 Part 2 :
    """
    def setUp(self):
        self.create_record(client_host, client_port, 'msf_c2', 'res.partner', {'name' : 'msf_common'})
    
    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c2', 'res.partner', 'msf_common')
        self.change_rule_group('MSF_partner', 'International')
        
    def runTest(self):
        self.change_rule_group('MSF_partner', 'Mission 1' )
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p1')
        #check that msf_common does not exist in msf_p1
        self.check_model_data(client_host, client_port, 'msf_p1', 'res.partner', {'name' : 'msf_common'}, False )

class TestMissionProduct(TestMSF):
    """
        UCS1 : c2 has a product A1, synchronize at mission level, check that p2 and p3 
        has the product in db with common attributes with good value and local attribute with
        default value 
    """
    def setUp(self):
        parent_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome1', 
                            'code' : '11'})
        parent2_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome2', 
                            'code' : '12', 
                            'parent_id' : parent_id,
                            })
        parent3_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                          {'name' : 'nome3', 
                            'code' : '13',
                            'parent_id' : parent2_id
                            })
        parent4_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome4', 
                            'code' : '14', 
							'parent_id' : parent3_id
                            })
        self.create_record(client_host, client_port, 'msf_c2', 'product.product', 
                           {'name' : 'm2_A1', 
                            'default_code' : 'local_ref', 
                            'standard_price' : 10.0,
                            'nomen_manda_0' : parent_id,
                            'nomen_manda_1' : parent2_id,
                            'nomen_manda_2' : parent3_id,
                            'nomen_manda_3' : parent4_id,
                            })
    def runTest(self):
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.check_model_data(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'm2_A1', 'standard_price' : 10.0, 'default_code' : False })
        self.check_model_data(client_host, client_port, 'msf_p3', 'product.product', {'name' : 'm2_A1', 'standard_price' : 10.0, 'default_code' : False })
    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c2', 'product.product', 'm2_A1')
        self.delete_record(client_host, client_port, 'msf_p2', 'product.product', 'm2_A1')
        self.delete_record(client_host, client_port, 'msf_p3', 'product.product', 'm2_A1')
        
class TestLocalProduct(TestMSF):
    """
        UCS2 : c2 has a product A2, synchronize at mission level, check that p2 and p3 
        has the product in db with common attributes with good value and local attribute with
        default value 
    """
    def setUp(self):
        parent_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome11', 
                            'code' : '111'})
        parent2_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome21', 
                            'code' : '121', 
                            'parent_id' : parent_id,
                            })
        parent3_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                          {'name' : 'nome31', 
                            'code' : '131',
                            'parent_id' : parent2_id
                            })
        parent4_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome41', 
                            'code' : '141', 
                            'parent_id' : parent3_id
                            })
        self.create_record(client_host, client_port, 'msf_c2', 'product.product', 
                           {'name' : 'local_A2', 
                            'standard_price' : 5.0,
                            'nomen_manda_0' : parent_id,
                            'nomen_manda_1' : parent2_id,
                            'nomen_manda_2' : parent3_id,
                            'nomen_manda_3' : parent4_id,
                            })
    def runTest(self):
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.check_model_data(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'local_A2'}, False)
        self.check_model_data(client_host, client_port, 'msf_p3', 'product.product', {'name' : 'local_A2'}, False)
    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c2', 'product.product', 'local_A2')

class TestSectionProduct(TestMSF):
    """
        UCS3 : c1 has a product A3, synchronize at section level, check that c2, c3, p1, p2 and p3 
        has the product in db with common attributes with good value and local attribute with
        default value 
    """
    def setUp(self):
        parent_id = self.create_record(client_host, client_port, 'msf_c1', 'product.nomenclature', 
                           {'name' : 'nome111', 
                            'code' : '222'})
        parent2_id = self.create_record(client_host, client_port, 'msf_c1', 'product.nomenclature', 
                           {'name' : 'nome211', 
                            'code' : '223', 
                            'parent_id' : parent_id,
                            })
        parent3_id = self.create_record(client_host, client_port, 'msf_c1', 'product.nomenclature', 
                          {'name' : 'nome311', 
                            'code' : '224',
                            'parent_id' : parent2_id
                            })
        parent4_id = self.create_record(client_host, client_port, 'msf_c1', 'product.nomenclature', 
                           {'name' : 'nome411', 
                            'code' : '225', 
                            'parent_id' : parent3_id
                            })
        self.create_record(client_host, client_port, 'msf_c1', 'product.product', 
                           {'name' : 's1_A3', 
                            'default_code' : 'local_ref', 
                            'standard_price' : 7.53,
                            'nomen_manda_0' : parent_id,
                            'nomen_manda_1' : parent2_id,
                            'nomen_manda_2' : parent3_id,
                            'nomen_manda_3' : parent4_id,})
    def runTest(self):
        self.synchronize(client_host, client_port, 'msf_c1')
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_c3')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.check_model_data(client_host, client_port, 'msf_c2', 'product.product', {'name' : 's1_A3', 'standard_price' : 7.53, 'default_code' : False })
        self.check_model_data(client_host, client_port, 'msf_c3', 'product.product', {'name' : 's1_A3', 'standard_price' : 7.53, 'default_code' : False })
        self.check_model_data(client_host, client_port, 'msf_p1', 'product.product', {'name' : 's1_A3', 'standard_price' : 7.53, 'default_code' : False })
        self.check_model_data(client_host, client_port, 'msf_p2', 'product.product', {'name' : 's1_A3', 'standard_price' : 7.53, 'default_code' : False })
        self.check_model_data(client_host, client_port, 'msf_p3', 'product.product', {'name' : 's1_A3', 'standard_price' : 7.53, 'default_code' : False })
    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c1', 'product.product', 's1_A3')
        self.delete_record(client_host, client_port, 'msf_c2', 'product.product', 's1_A3')
        self.delete_record(client_host, client_port, 'msf_c3', 'product.product', 's1_A3')
        self.delete_record(client_host, client_port, 'msf_p1', 'product.product', 's1_A3')
        self.delete_record(client_host, client_port, 'msf_p2', 'product.product', 's1_A3')
        self.delete_record(client_host, client_port, 'msf_p3', 'product.product', 's1_A3')
        
class TestMissionAttributeProduct(TestMSF):
    def setUp(self):
        parent_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome13', 
                            'code' : '311'})
        parent2_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome23', 
                            'code' : '312', 
                            'parent_id' : parent_id,
                            })
        parent3_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                          {'name' : 'nome33', 
                            'code' : '313',
                            'parent_id' : parent2_id
                            })
        parent4_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome43', 
                            'code' : '314', 
                            'parent_id' : parent3_id
                            })
        self.create_record(client_host, client_port, 'msf_c2', 'product.product', 
                           {'name' : 'm2_A1', 
                            'default_code' : 'local_ref', 
                            'standard_price' : 10.0,
                            'nomen_manda_0' : parent_id,
                            'nomen_manda_1' : parent2_id,
                            'nomen_manda_2' : parent3_id,
                            'nomen_manda_3' : parent4_id,})
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.synchronize(client_host, client_port, 'msf_p2')
    def runTest(self):
        self.check_model_data(client_host, client_port, 'msf_p3', 'product.product', {'name' : 'm2_A1', 'sale_ok' : True, 'purchase_ok' : True })
        self.check_model_data(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'm2_A1', 'sale_ok' : True, 'purchase_ok' : True })
        self.write_record(client_host, client_port, 'msf_c2', 'product.product', 
                           {'name' : 'm2_A1', 'purchase_ok' : False, 'sale_ok' : False})
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p3')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.check_model_data(client_host, client_port, 'msf_p3', 'product.product', {'name' : 'm2_A1', 'sale_ok' : False, 'purchase_ok' : False })
        self.check_model_data(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'm2_A1', 'sale_ok' : False, 'purchase_ok' : False })
    
    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c2', 'product.product', 'm2_A1')
        self.delete_record(client_host, client_port, 'msf_p2', 'product.product', 'm2_A1')
        self.delete_record(client_host, client_port, 'msf_p3', 'product.product', 'm2_A1')
        
class TestLocalAttributeProduct(TestMSF):
    def setUp(self):
        parent_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome14', 
                            'code' : '311'})
        parent2_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome24', 
                            'code' : '312', 
                            'parent_id' : parent_id,
                            })
        parent3_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                          {'name' : 'nome34', 
                            'code' : '313',
                            'parent_id' : parent2_id
                            })
        parent4_id = self.create_record(client_host, client_port, 'msf_c2', 'product.nomenclature', 
                           {'name' : 'nome44', 
                            'code' : '314', 
                            'parent_id' : parent3_id
                            })
        self.create_record(client_host, client_port, 'msf_c2', 'product.product', 
                           {'name' : 'm2_A1', 
                            'default_code' : 'local_ref', 
                            'standard_price' : 10.0,
                            'nomen_manda_0' : parent_id,
                            'nomen_manda_1' : parent2_id,
                            'nomen_manda_2' : parent3_id,
                            'nomen_manda_3' : parent4_id,})
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_p2')
    def runTest(self):
        self.check_model_data(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'm2_A1', 'default_code' : False})
        self.write_record(client_host, client_port, 'msf_c2', 'product.product', 
                           {'name' : 'm2_A1', 'default_code' : 'still_local_ref'})
        self.synchronize(client_host, client_port, 'msf_c2')
        self.synchronize(client_host, client_port, 'msf_p1')
        self.synchronize(client_host, client_port, 'msf_p2')
        self.check_model_data(client_host, client_port, 'msf_p1', 'product.product', {'name' : 'm2_A1'}, False) #check the record doesn't exist
        self.check_model_data(client_host, client_port, 'msf_p2', 'product.product', {'name' : 'm2_A1', 'default_code' : False })
    
    def tearDown(self):
        self.delete_record(client_host, client_port, 'msf_c2', 'product.product', 'm2_A1')
        self.delete_record(client_host, client_port, 'msf_p2', 'product.product', 'm2_A1')
        
if __name__ == '__main__':
    test = unittest.TestSuite()
    test.addTest(TestDataSyncBase())
    test.addTest(TestNoRuleChange())
    test.addTest(TestRuleChange())
    #USE CASE SUpply
    test.addTest(TestMissionProduct())
    test.addTest(TestLocalProduct())
    test.addTest(TestSectionProduct())
    test.addTest(TestMissionAttributeProduct())
    test.addTest(TestLocalAttributeProduct())
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test)
