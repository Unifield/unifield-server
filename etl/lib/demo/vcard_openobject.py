#!/usr/bin/python
import sys
sys.path.append('..')

import etl

filevcard=etl.connector.localfile('input/contacts.vcf')
vcard_in1= etl.component.input.vcard_in(filevcard)
ooconnector = etl.connector.openobject_connector('http://localhost:8069', 'trunk', 'admin', 'a', con_type='xmlrpc')

map = etl.component.transform.map({'main':{
    'id': "tools.uniq_id(main.get('org', 'anonymous'), prefix='partner_')",
    'address_id': "tools.uniq_id(main.get('fn', 'anonymous'), prefix='contact_')",
    'name': "main.get('org',[anonymous])[0]",
    'contact_name': "main.get('fn','anonymous')",
    'email': "main.get('email','')"
}})

oo_out= etl.component.output.openobject_out(
     ooconnector,
     'res.partner',
     ['id','name']
)

oo_out2= etl.component.output.openobject_out(
     ooconnector,
     'res.partner.address',
     {'name': 'contact_name', 'id':'address_id', 'partner_id:id':'id','email':'email'}
)
log1=etl.component.transform.logger(name='vCard->Oo')

tran=etl.transition(vcard_in1,map)
tran=etl.transition(map,log1)
tran=etl.transition(log1,oo_out)
tran=etl.transition(oo_out,oo_out2)
job1=etl.job([oo_out2])
job1.run()
