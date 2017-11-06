# -*- encoding: utf-8 -*-
import xmlrpclib
import base64


dbname='partial12-finance_HQ1C1'
user='admin'
pwd = 'admin'
host = '127.0.0.1'
xmlrpcport = 8069

url = 'http://%s:%s/xmlrpc/' % (host, xmlrpcport)
sock = xmlrpclib.ServerProxy(url + 'common')
uid = sock.login(dbname, user, pwd)
sock = xmlrpclib.ServerProxy(url + 'object')
proc_obj = 'stock.incoming.processor'
wiz_obj = 'wizard.import.in.simulation.screen'
pick_id = 1837
#import_file = 'IN_388.xml'
#type='xml'
#import_file='IN.xls'
import_file='IN.390.xls'
type='excel'


#pick_id = 1798 #IN_388
proc_id =  sock.execute(dbname, uid, pwd, proc_obj, 'create', {'picking_id': pick_id})
proc_info = sock.execute(dbname, uid, pwd, proc_obj, 'launch_simulation_pack', proc_id)
f = open(import_file, 'r').read()

wiz_id = sock.execute(dbname, uid, pwd, wiz_obj, 'write', [proc_info['res_id']], {'filetype': type, 'file_to_import': base64.encodestring(f)})
sock.execute(dbname, uid, pwd, wiz_obj, 'launch_simulate', [proc_info['res_id']])
toto = sock.execute(dbname, uid, pwd, wiz_obj, 'launch_import', [proc_info['res_id']])
