##############################################################################
#
# Copyright (c) 2005-2006 TINY SPRL. (http://tiny.be) All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import time
import wizard
import pooler

dates_form = '''<?xml version="1.0"?>
<form string="Partner Account">
    <field name="debit_name"/><newline/>
    <field name="debit_parent" colspan="4"/>
    <field name="credit_name"/><newline/>
    <field name="credit_parent" colspan="4"/>
</form>'''

dates_fields = {
    'debit_name': {'string':'Receivable Account', 'type':'char', 'size':64, 'required':True},
    'credit_name': {'string':'Payable Account', 'type':'char', 'size':64,  'required':True},
    'debit_parent': {'string':'Account Receivable', 'type':'many2one', 'relation': 'account.account', 'required':True},
    'credit_parent': {'string':'Account Payable', 'type':'many2one', 'relation': 'account.account', 'required':True},
}

def get_name(self, cr, uid, data, context={}):
    partner = pooler.get_pool(cr.dbname).get('res.partner')
    account = pooler.get_pool(cr.dbname).get('account.account')
    
    name = partner.read(cr, uid, [data['id']], ['name'])[0]['name']
    
    
    res = {
        'debit_name':name + ' - Receivable', 
        'credit_name':name + ' - Payable', 'name':name
    }
    
    id1 = False
    id2 = False
    try:
        id1 = account.search(cr, uid, [('type','=','receivable')])[0]
        res['debit_parent'] = id1
    except:
        pass
    
    try:
        id2 = account.search(cr, uid, [('type','=','payable')])[0]
        res['credit_parent'] = id2
    except:
        pass
    
    return res

    
def create_accout(self, cr, uid, data, context={}):
    dname = data['form']['debit_name'] 
    cname = data['form']['credit_name']
    dacc = data['form']['debit_parent']
    cacc = data['form']['credit_parent']
    
    account = pooler.get_pool(cr.dbname).get('account.account')
    type = pooler.get_pool(cr.dbname).get("account.account.type")
    
    lia_id = type.search(cr, uid, [('code','=','liability')])
    ass_id = type.search(cr, uid, [('code','=','asset')])
    
    code = account.read(cr, uid, [dacc], ['code'])[0]['code']    
    debit_id = account.create(cr, uid, {
        'code': str(code) + data['form']['name'],
        'name':dname,
        'parent_id':dacc,
        'type':'receivable',
        'reconcile':True,
        'user_type':ass_id[0]
    })
    
    code = account.read(cr, uid, [cacc], ['code'])[0]['code']    
    credit_id = account.create(cr, uid, {
        'code': str(code) + data['form']['name'],
        'name':cname,
        'parent_id':cacc,
        'type':'payable',
        'reconcile':True,
        'user_type':lia_id[0]
    })
    
    partner = pooler.get_pool(cr.dbname).get('res.partner')
    partner.write(cr, uid, data['id'], {
        'property_account_receivable':debit_id, 
        'property_account_payable':credit_id
    })
    
    return {}

class Account(wizard.interface):
    states = {
        'init': {
            'actions': [get_name],
            'result': {
                'type': 'form',
                'arch': dates_form,
                'fields': dates_fields,
                'state': [
                    ('end', 'Cancel'),
                    ('next', 'Create Account')
                ]
            }
        },
        
        'next': {
            'actions': [create_accout],
            'result': {
                'type': 'state',
                'state': 'end'
            }
        },
    }
Account('partner.account.create')
