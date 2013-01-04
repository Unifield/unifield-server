#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Max Mumford 
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import datetime
import openerplib

# variables
NUMBER_OF_WRITES = 100
AS_ADMIN = False
ADMIN_PASSWORD = 'a'

# init
if not AS_ADMIN:
    connection = openerplib.get_connection(hostname="localhost", database="access_right", login="msf_access_rights_benchmarker", password="benchmark_it")
else:
    connection = openerplib.get_connection(hostname="localhost", database="access_right", login="admin", password=ADMIN_PASSWORD)

field_access_rule_pool = connection.get_model('msf_access_rights.field_access_rule')
field_access_rule_line_pool = connection.get_model('msf_access_rights.field_access_rule_line')

user_pool = connection.get_model("res.users")

model_pool = connection.get_model("ir.model")
user_model_id = model_pool.search([('model','=','res.users')])[0]

instance_pool = connection.get_model('msf.instance')
instance_level_search = instance_pool.search([('level', '!=', False)])
instance_level = 'project'

# create a rule to benchmark against (unless already exists)
field_access_rule_id = field_access_rule_pool.search([('name','=','benchmark_users')])

if not field_access_rule_id:
    
    rule_values = {
      'name':'benchmark_users',
      'model_id':user_model_id,
      'instance_level':instance_level,
      'filter':False,
      'domain_text':False,
      'group_ids':False,
      'state':'filter_validated',
      'active':'1'
    }
    
    field_access_rule_id = field_access_rule_pool.create(rule_values)
    
else:
    field_access_rule_id = field_access_rule_id[0]
    
existing_lines = field_access_rule_line_pool.search([('field_access_rule','=',field_access_rule_id)])
if existing_lines:
    field_access_rule_line_pool.unlink(existing_lines)
    
field_access_rule_pool.generate_rules_button([field_access_rule_id])

field_access_rule = field_access_rule_pool.read(field_access_rule_id)
field_access_rule_lines = field_access_rule_line_pool.read(field_access_rule['field_access_rule_line_ids'])

lines_to_edit = [line['id'] for line in field_access_rule_lines if \
                 line['field_name'] == 'address_id' \
                 or line['field_name'] == 'user_email' \
                 or line['field_name'] == 'action_id']

try:
    field_access_rule_line_pool.write(lines_to_edit, {"value_not_synchronized_on_write":"1"})
except:
    field_access_rule_pool.unlink(field_access_rule_id)
    raise
    
# create the user to write on (unless already exists)
user_id = user_pool.search([('name','=','msf_access_rights_benchmark')])

if not user_id:
    
    user_values = {
        'name':'msf_access_rights_benchmark',
        'login':'msf_access_rights_benchmark',
        'user_email':'benchmark@test.com',
    }
    
    user_id = user_pool.create(user_values)
else:
    user_id = user_id[0]

# save timestamp
start = datetime.datetime.now()
print '========================================================'
print 'STARTING %s WRITES. AS_ADMIN=%s' % (NUMBER_OF_WRITES, AS_ADMIN)

# loop write
even_data = {'user_email':'benchmark1@test.com'}
odd_data = {'user_email':'benchmark@test.com'}

context = {'sync_data':True, 'applyToAdmin':True}

for i in range(0, NUMBER_OF_WRITES):
    if i % 2 == 0:
        user_pool.write(user_id, even_data)
    else:
        user_pool.write(user_id, odd_data)

# print time taken
end = datetime.datetime.now()
time_taken = end - start
print 'TIME TAKEN TO PERFORM %s WRITES: %s:%s (seconds:milliseconds)' % (NUMBER_OF_WRITES, time_taken.seconds, time_taken.microseconds / 1000)
print '========================================================'

# delete test user
field_access_rule_pool.unlink([field_access_rule_id])
user_pool.unlink([user_id])