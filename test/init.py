#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author : OpenERP
import rpc
import sys
import threading

from config import *

client_module = ['sync_client', 'sync_client_test', 'sync_so', 'purchase', 'account_voucher', 'account_analytic_plans'] # 
server_module = ['sync_server', 'sync_server_test']

def get_proxy(host, port, database, model):
    connector = rpc.NetRPCConnector(host, port)
    cnx = rpc.Connection(connector, database, login, password, uid)
    return rpc.Object(cnx, model)

def init():
    create_database(client_host, client_port, 'msf_c1')
    create_database(client_host, client_port, 'msf_c2')
    create_database(client_host, client_port, 'msf_c3')
    create_database(client_host, client_port, 'msf_p1')
    create_database(client_host, client_port, 'msf_p2')
    create_database(client_host, client_port, 'msf_p3')
    create_database(server_host, server_port, server_db)
    
def init_client_module(host, port, list):
    for client in list:
        module_install(host, port, client, client_module)
        module_init(host, port, client)
    
def init_module():
    client_list = ['msf_c1', 'msf_c2', 'msf_c3', 'msf_p1', 'msf_p2', 'msf_p3']
    #client_list = ['msf_c1']
    thread_list = []

    t = threading.Thread(None, init_client_module, None, (client_host, client_port, client_list), {})
    t.start()
    
    st = threading.Thread(None, module_install, None, (server_host, server_port, 'server_test', server_module,), {})
    st.start()
    thread_list.append(st)

    for t in thread_list:
        t.join()
        
def clean():
    drop_database(client_host, client_port, 'msf_c1')
    drop_database(client_host, client_port, 'msf_c2') 
    drop_database(client_host, client_port, 'msf_c3')
    drop_database(client_host, client_port, 'msf_p1')
    drop_database(client_host, client_port, 'msf_p2')
    drop_database(client_host, client_port, 'msf_p3')
    drop_database(server_host, server_port, 'server_test')
    
def module_install(host, port, db, module_list):
    print "install module at ", host, port, db, module_list
    proxy_upgrade = get_proxy(host, port, db, "base.module.upgrade")
    proxy = get_proxy(host, port, db, 'ir.module.module')
    ids = proxy.search([('name','in', module_list)])
    proxy.button_install(ids)
    proxy_upgrade.upgrade_module(False)
    installed_ids = proxy.search([('name', 'in', module_list), ('state', '=', 'installed')])
    assert ids == installed_ids, 'Some module failed to install in db %s \n %s, %s' % (db, ids, installed_ids)
   
def module_init(host, port, db): 
    proxy_company = get_proxy(host, port, db, 'base.setup.company')
    co_id = proxy_company.create({'name' : db, 'currency' : 2})
    proxy_company.action_next([co_id])
    
    proxy_account = get_proxy(host, port, db, 'account.installer')
    wiz_id = proxy_account.create({})
    proxy_account.action_next([wiz_id])

def create_database(host, port, db_name):
    print "create" , host, port, db_name
    connector = rpc.NetRPCConnector(host, port)
    rpc.Database(connector).create('admin', db_name, False, 'en_US', 'admin')
    
def drop_database(host, port, db_name):
    print "drop" , host, port, db_name
    connector = rpc.NetRPCConnector(host, port)
    rpc.Database(connector).drop('admin', db_name)
    
if __name__ == '__main__':
    if sys.argv and sys.argv[1] == 'init':
        init()
    if sys.argv and sys.argv[1] == 'module':
        init_module()
    if sys.argv and sys.argv[1] == 'clean':
        clean()
