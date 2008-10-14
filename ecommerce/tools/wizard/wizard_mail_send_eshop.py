# -*- encoding: utf-8 -*-
import wizard
import netsvc
import pooler
import time
import mx.DateTime
import datetime
import os
from osv import osv
import tools
import binascii
import base64
from email import Encoders

sent_dict={}
not_sent=[]

mail_send_form = '''<?xml version="1.0"?>
<form string="Mail to Customer">
    <field name = "partner_id"/>
    <newline/>
    <field name="subject"/>
    <newline/>
    <field name="message"/>
    <newline/>
    <field name ="attachment"/>
</form>'''

mail_send_fields = {
    'partner_id': {'string':'Customer','type': 'many2many', 'relation': 'res.partner','domain':"[('category_id','in',[1])]"},
    'subject': {'string':'Subject', 'type':'char', 'size':64, 'required':True},
    'message': {'string':'Message', 'type':'text', 'required':True},
    'attachment':{'string' : 'Attachment','type':'many2one','relation':'ir.attachment'}
}
   
finished_form='''<?xml version="1.0"?>
<form string="Mail send ">
    <label string="Operation Completed " colspan="4"/>
    <field name ="mailsent" width="300"/>
    <field name ="mailnotsent" width="300"/>
</form>''';

finished_fields = {
    'mailsent': {'string':'Mail Sent to', 'type':'text'},
    'mailnotsent': {'string':'Mail Not sent', 'type':'text'}
}

class wiz_send_email_eshop(wizard.interface):
 
    def _send_reminder(self, cr, uid, data, context):
            attach=data['form']['attachment']
        
            partner = data['form']['partner_id'][0][2]
         
            flag_success = True
            if partner:
                res = pooler.get_pool(cr.dbname).get('res.partner').browse(cr,uid,partner)
                for partner in res:
                    if partner.address and not partner.address[0].email:
                            not_sent.append(partner.name)
                    for adr in partner.address:
                      
                        if adr.email:
                           
                            sent_dict[partner.name]=adr.email
                            name = adr.name or partner.name
                            to = '%s <%s>' % (name, adr.email)
                            mail_from= 'priteshmodi.eiffel@yahoo.co.in'
                           
                            attach_ids = pooler.get_pool(cr.dbname).get('ir.attachment').search(cr, uid,
                            [('res_model', '=', 'ecommerce.shop'),
                                ('res_id', '=', data['ids'][0])])
                           
                            res_atc = pooler.get_pool(cr.dbname).get('ir.attachment').read(cr, uid,
                                        attach_ids, ['datas_fname','datas'])
                            res_atc = map(lambda x: (x['datas_fname'],
                                    base64.decodestring(x['datas'])), res_atc)
                            tools.email_send_attach(mail_from, [to], data['form']['subject'], data['form']['message'],attach=res_atc)
                    
            return 'finished';

        
    def get_mail_dtl(self, cr, uid, data, context):
            dtl = len(sent_dict)
            cust_get_mail = []
            cust_not_get_mail=[]
            mail_value = ''
            not_mail = ''
            for items in sent_dict:
                cust_get_mail.append(items) 
                mail_value = mail_value+ ','+items
                
            for items_not in not_sent:
                cust_not_get_mail.append(items_not)
                not_mail = not_mail+ ','+items_not
            return {'mailsent':str(mail_value),'mailnotsent':str(not_mail)}

    states = {
                    'init': {
                    'actions': [],
                    'result': {'type':'form', 'arch':mail_send_form, 'fields':mail_send_fields, 'state':[('end','Cancel'),('connect','Send Mail')]}
                    },
                     
            'connect': {
                    'actions': [],
                    'result': {'type':'choice', 'next_state': _send_reminder},
                     },
       
            'finished': {
                    'actions': [get_mail_dtl],
                    'result': {'type':'form', 'arch': finished_form, 'fields':finished_fields,'state':[('end','OK')]}
                        },
            }
  
wiz_send_email_eshop('customer.send.mail.eshop') 


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

