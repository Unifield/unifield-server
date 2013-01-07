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

import sys
from optparse import OptionParser
import webbrowser
import datetime
import openerplib
import matplotlib.pyplot as plt
import itertools

# command line params
parser = OptionParser()

parser.add_option('-c', '--create', action='store_true', help='Test the create function')
parser.add_option('-w', '--write', action='store_true', help='Test the write function')
parser.add_option('-f', '--fvg', '--fields-view-get', action='store_true', dest='fvg', help='Test the fields_view_get function')
parser.add_option('-n', '-i', '--number-of-iterations',  default=50, type='int', dest='iterations', help='The number of creates/writes to perform for the benchmark')
parser.add_option('-r', '--number-of-rules', default=10, type='int', dest='rules', help='The number of field access rules to create')
parser.add_option('-a', '--hostaddress', dest='host', default="localhost", help='The address of the host')
parser.add_option('-d', '--database', default="access_right", help='The name of the database')
parser.add_option('-u', '--admin-username', dest='username', default="msf_access_rights_benchmarker", help='The username for the account to use to login to OpenERP')
parser.add_option('-p', '--admin-password', dest='password', default="benchmark_it", help='The password for the account to use to login to OpenERP')

options, args = parser.parse_args()

if not options.create and not options.write and not options.fvg:
    options.write = options.create = options.fvg = True 
    
# init connection and pools 
connection = openerplib.get_connection(hostname=options.host, database=options.database, login=options.username, password=options.password)

field_access_rule_pool = connection.get_model('msf_access_rights.field_access_rule')
field_access_rule_line_pool = connection.get_model('msf_access_rights.field_access_rule_line')

user_pool = connection.get_model("res.users")

model_pool = connection.get_model("ir.model")
user_model_id = model_pool.search([('model','=','res.users')])[0]

instance_pool = connection.get_model('msf.instance')
instance_level_search = instance_pool.search([('level', '!=', False)])
instance_level = 'project'

# create rules to benchmark against
field_access_rule_ids = field_access_rule_pool.search([('name','like','benchmark_users_')])

if field_access_rule_ids:
    field_access_rule_pool.unlink(field_access_rule_ids)
    
field_access_rule_ids = []

for i in range(0, options.rules):
    rule_values = {
      'name':'benchmark_users_' + str(i),
      'model_id':user_model_id,
      'instance_level':instance_level,
      'filter':False,
      'domain_text':False,
      'group_ids':False,
      'state':'filter_validated',
      'active':'1'
    }
    field_access_rule_ids.append(field_access_rule_pool.create(rule_values))
    
# generate field access rule lines and edit them to have appropriate settings for tests
existing_lines = field_access_rule_line_pool.search([('field_access_rule','in',field_access_rule_ids)])
if existing_lines:
    field_access_rule_line_pool.unlink(existing_lines)
    
field_access_rule_pool.generate_rules_button(field_access_rule_ids)

field_access_rules = field_access_rule_pool.read(field_access_rule_ids)

field_access_rule_line_ids = list(itertools.chain(*[rule['field_access_rule_line_ids'] for rule in field_access_rules]))
field_access_rule_lines = field_access_rule_line_pool.read(field_access_rule_line_ids)

lines_to_edit = [line['id'] for line in field_access_rule_lines if \
                 line['field_name'] == 'address_id' \
                 or line['field_name'] == 'user_email' \
                 or line['field_name'] == 'action_id']

try:
    field_access_rule_line_pool.write(lines_to_edit, {"value_not_synchronized_on_write":"1"})
except:
    field_access_rule_pool.unlink(field_access_rule_ids)
    raise

# init write
if options.write:
        
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
    print 'STARTING %s WRITES AS %s' % (options.iterations, options.username)
    
    # loop write
    even_data = {'user_email':'benchmark1@test.com'}
    odd_data = {'user_email':'benchmark@test.com'}
    
    for i in range(0, options.iterations):
        if i % 2 == 0:
            user_pool.write(user_id, even_data)
        else:
            user_pool.write(user_id, odd_data)
    
    # print time taken
    end = datetime.datetime.now()
    time_taken = end - start
    print 'TIME TAKEN TO PERFORM %s WRITES: %s.%s (seconds)' % (options.iterations, time_taken.seconds, time_taken.microseconds)
    per_write_time_taken = time_taken / options.iterations
    print '1 WRITE = %s.%06d (seconds)' % (per_write_time_taken.seconds, per_write_time_taken.microseconds)
    print '========================================================'
    
    # delete test user
    user_pool.unlink([user_id])
    
# init create
if options.create:
    # save timestamp
    start = datetime.datetime.now()
    print '========================================================'
    print 'STARTING %s CREATES AS %s' % (options.iterations, options.username)
    
    created_user_ids = []
    
    # loop create
    for i in range(0, options.iterations):
        user_values = {
            'name':'msf_access_rights_benchmark_create_' + str(i),
            'login':'msf_access_rights_benchmark_create_' + str(i),
            'user_email':'benchmark%s@test.com' % str(i),
        }
        created_user_ids.append(user_pool.create(user_values))
    
    # print time taken
    end = datetime.datetime.now()
    time_taken = end - start
    print 'TIME TAKEN TO PERFORM %s CREATES: %s.%s (seconds)' % (options.iterations, time_taken.seconds, time_taken.microseconds)
    per_create_time_taken = time_taken / options.iterations
    print '1 CREATE = %s.%06d (seconds)' % (per_create_time_taken.seconds, per_create_time_taken.microseconds)
    print '========================================================'
    
    # delete created users
    user_pool.unlink(created_user_ids)
    
# init fields_view_get
if options.fvg:
    # save timestamp
    start = datetime.datetime.now()
    print '========================================================'
    print 'STARTING %s FIELDS_VIEW_GET AS %s' % (options.iterations, options.username)
    
    # make requests in loop
    for i in range(0, options.iterations):
        user_pool.fields_view_get()
    
    # print time taken
    end = datetime.datetime.now()
    time_taken = end - start
    print 'TIME TAKEN TO PERFORM %s FIELDS_VIEW_GET: %s.%s (seconds)' % (options.iterations, time_taken.seconds, time_taken.microseconds)
    per_fvg_time_taken = time_taken / options.iterations
    print '1 FVG = %s.%06d (seconds)' % (per_fvg_time_taken.seconds, per_fvg_time_taken.microseconds)
    print '========================================================'
    
# cleanup
field_access_rule_pool.unlink(field_access_rule_ids)