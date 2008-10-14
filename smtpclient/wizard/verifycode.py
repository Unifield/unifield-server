# -*- encoding: utf-8 -*-
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

import wizard
import pooler

form = '''<?xml version="1.0"?>
<form string="Verify Code">
    <field name="code" colspan="4"/>
</form>'''

fields = {
    'code': {'string': 'Verification Code','required':True,  'size': 255 , 'type': 'char', 'help': 'Enter verification code thay you get in your Verification Email'}
}

class verifycode(wizard.interface):
    
    def checkcode(self, cr, uid, data, context):
        
        state = pooler.get_pool(cr.dbname).get('email.smtpclient').browse(cr, uid, data['id'], context).state
        if state == 'confirm':
            raise Exception, 'Server already Verified!!!'
            
        code = pooler.get_pool(cr.dbname).get('email.smtpclient').browse(cr, uid, data['id'], context).code
        if code == data['form']['code']:
            pooler.get_pool(cr.dbname).get('email.smtpclient').write(cr, uid, [data['id']], {'state':'confirm'})
        else:
            raise Exception, 'Verification Failed, Invalid Verification Code!!!'
        return {}
    
    states = {
        'init': {
            'actions': [],
            'result': {'type':'form', 'arch':form, 'fields':fields, 'state':[('end','Cancel'),('check','Verify Code')]}
        },
        'check': {
            'actions': [checkcode],
            'result': {'type':'state', 'state':'end'}
        }
    }
verifycode('email.verifycode')


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

