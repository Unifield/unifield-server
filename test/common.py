# -*- coding: utf-8 -*-
'''
Created on 17 août 2011

@author: openerp
'''

from config import *
import rpc
import unittest

def get_proxy(host, port, database):
    connector = rpc.NetRPCConnector(host, port)
    cnx = rpc.Connection(connector, database, login, password, uid)
    return rpc.Object(cnx, 'sync.client.test')

def get_server_proxy():
    connector = rpc.NetRPCConnector(server_host, server_port)
    cnx = rpc.Connection(connector, server_db, login, password, uid)
    return rpc.Object(cnx, 'sync.server.test')


class TestMSF(unittest.TestCase):
    def single_test_connection(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        uid = proxy.set_connection(db_name, server_db, server_host, server_port, 'msf', 5)
        self.assertNotEqual(uid, 0)
        
    def single_activation_test(self, host, port, db_name, parent_name):
        proxy = get_proxy(host, port, db_name)
        res_parent = proxy.activate(db_name)
        self.assertEqual(res_parent, parent_name) 
        self.single_activated_test(db_name)
        
    def single_register_test(self, host, port, db_name, parent_name, group_name_list):
        proxy = get_proxy(host, port, db_name)
        res = proxy.register(db_name, parent_name, default_email, group_name_list)
        self.assertTrue(res)
        self.single_registered_test(db_name)
        
    def single_activated_test(self, name):  
        sproxy = get_server_proxy()
        res = sproxy.check_validated(name)
        self.assertTrue(res)
        
    def single_registered_test(self, name):
        sproxy = get_server_proxy()
        res = sproxy.check_register(name)
        self.assertTrue(res)
        
    def single_activate_by_parent(self, host, port, db_name, child_name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.activate_by_parent(child_name)
        self.assertTrue(res)
        self.single_activated_test(child_name)
        
    """
        Data synchronization
    """
    def synchronize(self, host, port, db_name):
        proxy = get_proxy(host, port, db_name)
        proxy.synchronize()
        
    def check_model_data(self, host, port, db_name, model, data, result=True):
        proxy = get_proxy(host, port, db_name)
        res = proxy.check_model_info(model, data)
        if result:
            self.assertTrue(res)
        else:
            self.assertFalse(res)
    def create_record(self, host, port, db_name, model, data):
        proxy = get_proxy(host, port, db_name)
        res = proxy.create_record(model, data)
        self.assertTrue(res)
        return res
        
    def write_record(self, host, port, db_name, model, data):
        proxy = get_proxy(host, port, db_name)
        res = proxy.write_record(model, data)
        self.assertTrue(res)
        
    def delete_record(self, host, port, db_name, model, name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.delete_record(model, name)
        self.assertTrue(res)
        
    def change_rule_group(self, rule_name, group_name):
        sproxy = get_server_proxy()
        res = sproxy.change_rule_group(rule_name, group_name)
        self.assertTrue(res)
        
    def get_record_id(self, host, port, db_name, model, name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.get_record_id(model, name)
        return res
    
    def get_record_data(self, host, port, db_name, model, id, fields):
        proxy = get_proxy(host, port, db_name)
        res = proxy. get_record_data(model, id, fields)
        return res
    
class TestMSFMessage(TestMSF):  
    def create_po(self, host, port, db_name, supplier_name, po_name, product_name):
        product_id = self.get_record_id(host, port, db_name, 'product.product', product_name)
        partner_id = self.get_record_id(host, port, db_name, 'res.partner', supplier_name)
        
        address_id = self.get_record_id(host, port, db_name, 'res.partner.address', supplier_name)
        self.create_record(host, port, db_name, 'purchase.order', {
                                                               'name' : po_name,
                                                               'partner_id' : partner_id, 
                                                               'pricelist_id' : 1, 
                                                               'partner_address_id' :  address_id,
                                                               'location_id' : 1,
                                                               'state' : 'confirmed',
                                                               'order_line' : [(0,0, 
                                                                         {'name' : product_name, 
                                                                          'product_id' : product_id,
                                                                          'product_qty' : 10, 
                                                                          'product_uom' : 1, 
                                                                          'price_unit' : 14.0, 
                                                                          'date_planned' : '2011-10-10'}
                                                                    )]
                                                               })
        
    def create_so(self, host, port, db_name, client_name, so_name, product_name):
        product_id = self.get_record_id(host, port, db_name, 'product.product', product_name)
        partner_id = self.get_record_id(host, port, db_name, 'res.partner', client_name)
        address_id = self.get_record_id(host, port, db_name, 'res.partner.address', client_name)
        res_id = self.create_record(host, port, db_name, 'sale.order', {
                                                               'name' : so_name,
                                                               'partner_id' : partner_id, 
                                                               'pricelist_id' : 1, 
                                                               'partner_order_id' :  address_id,
                                                               'partner_invoice_id' : address_id,
                                                               'partner_shipping_id' : address_id,
                                                               'location_id' : 1,
                                                               'order_line' : [(0,0, 
                                                                         {'name' : product_name, 
                                                                          'product_id' : product_id,
                                                                          'product_qty' : 10, 
                                                                          'product_uom' : 1, 
                                                                          'price_unit' : 14.0, 
                                                                          'date_planned' : '2011-10-10'})]})
                                                                        
        self.exec_wkf(host, port, db_name, 'sale.order', 'order_confirm', res_id)
        
    def check_model_data_like(self, host, port, db_name, model, data, result=True):
        proxy = get_proxy(host, port, db_name)
        res = proxy.check_model_info_like(model, data)
        if result:
            self.assertTrue(res)
        else:
            self.assertFalse(res)
            
    def confirm_so(self, host, port, db_name, ref):
        proxy = get_proxy(host, port, db_name)
        res = proxy.confirm_so(ref)
        self.assertTrue(res)
        
    def confirm_shippements(self, host, port, db_name, ref):
        proxy = get_proxy(host, port, db_name)
        res = proxy.confirm_shippements(ref)
        self.assertTrue(res)
        
    def confirm_incoming_shippements(self, host, port, db_name, name):
        proxy = get_proxy(host, port, db_name)
        res = proxy.confirm_incoming_shippements(name)
        self.assertTrue(res)
        
    def exec_wkf(self, host, port, db_name,  model, transition_name, id=0, name=None):
        proxy = get_proxy(host, port, db_name)
        proxy.exec_wkf(model, transition_name, id, name)
        