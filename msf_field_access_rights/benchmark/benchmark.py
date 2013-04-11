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
import datetime
import openerplib
import itertools
import pylab as pl
import os

# command line params
field_access_rule_ids = False
parser = OptionParser()

parser.add_option('-c', '--create', action='store_true', help='Test the create function')
parser.add_option('-w', '--write', action='store_true', help='Test the write function')
parser.add_option('-f', '--fvg', '--fields-view-get', action='store_true', dest='fvg', help='Test the fields_view_get function')
parser.add_option('-n', '-i', '--number-of-iterations',  default=30, type='int', dest='iterations', help='The number of creates/writes/fields_view_get to perform for the benchmark')
parser.add_option('-r', '--number-of-rules', default=10, type='int', dest='rules', help='The number of field access rules to create')
parser.add_option('-a', '--hostaddress', dest='host', default="localhost", help='The address of the host')
parser.add_option('-d', '--database', default="access_right", help='The name of the database')
parser.add_option('-u', '--admin-username', dest='username', default="msf_field_access_rights_benchmarker", help='The username for the account to use to login to OpenERP')
parser.add_option('-p', '--admin-password', dest='password', default="benchmark_it", help='The password for the account to use to login to OpenERP')
parser.add_option('-s', '--save-graphs', action='store_true', dest='save', help='Save graphs to physical files (In msf_field_access_rights/benchmark/graphs directory)')
parser.add_option('-o', '--file-prefix', dest='prefix', help='A prefix for the filenames when they are saved (In msf_field_access_rights/benchmark/graphs directory)')

options, args = parser.parse_args()

if not options.create and not options.write and not options.fvg:
    options.write = options.create = options.fvg = True
    
options.prefix = options.prefix or '' 
    
# init connection and pools 
connection = openerplib.get_connection(hostname=options.host, database=options.database, login=options.username, password=options.password)

field_access_rule_pool = connection.get_model('msf_field_access_rights.field_access_rule')
field_access_rule_line_pool = connection.get_model('msf_field_access_rights.field_access_rule_line')

user_pool = connection.get_model("res.users")

model_pool = connection.get_model("ir.model")
user_model_id = model_pool.search([('model','=','res.users')])[0]

def _get_instance_level():
    company_id = connection.get_model('res.users').read(connection.user_id)['company_id']
    company = connection.get_model('res.company').read(company_id[0])
    
    if 'instance_id' in company and company['instance_id']:
        instance = connection.get_model('msf.instance').read(company['instance_id'])
        
        instance_level = instance.get('level', False)
        
        if instance_level:
            if instance_level.lower() == 'section':
                instance_level = 'hq'
                
            return instance_level.lower()
        else:
            return False    
    else:
        return False

instance_level = _get_instance_level()

def create_rules():
    # create rules to benchmark against
    print '... creating %s rules' % options.rules
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
    
    print '... done'
    return field_access_rule_ids

# init create
def create():
    # save timestamp
    start = datetime.datetime.now()
    print '========================================================'
    print 'STARTING %s CREATES AS %s' % (options.iterations, options.username)
    
    created_user_ids = []
    
    # loop create
    for i in range(0, options.iterations):
        user_values = {
            'name':'msf_field_access_rights_benchmark_create_' + str(i),
            'login':'msf_field_access_rights_benchmark_create_' + str(i),
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
    
    return per_create_time_taken

def write():
        
    # create the user to write on (unless already exists)
    user_id = user_pool.search([('name','=','msf_field_access_rights_benchmark')])
    
    if not user_id:
        
        user_values = {
            'name':'msf_field_access_rights_benchmark',
            'login':'msf_field_access_rights_benchmark',
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
    
    return per_write_time_taken
    
# init fields_view_get
def fvg():
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
    
    return per_fvg_time_taken
    
def make_graph(graph_name, x, x_labels, y):
    fig = pl.figure()
    ax = pl.subplot(111)
    ax.bar(x, y, width=1)
    fig.canvas.manager.set_window_title(graph_name + " with %s iterations and %s rules" % (options.iterations, options.rules))
    pl.xticks(x, x_labels)
    pl.ylabel('Seconds per operation')
    
    if options.save:
        pl.savefig(options.prefix + " " + graph_name + ".png")
    else: 
        pl.show()
    
def friendly_time(td):
    if td.seconds > 0:
        return ((td.seconds * 1000000) + td.microseconds) / 1000000.0
    else:
        return td.microseconds / 1000000.0
    
if options.create:
    create_time = create()
    
if options.write:
    write_time = write()
    
if options.fvg:
    fvg_time = fvg()
    
field_access_rule_ids = create_rules()

if options.create:
    create_time_with_rules = create()

if options.write:
    write_time_with_rules = write()
    
if options.fvg:
    fvg_time_with_rules = fvg()
    
# cleanup
if field_access_rule_ids:
    print '... deleting %s rules' % options.rules
    field_access_rule_pool.unlink(field_access_rule_ids)
    print '... done'

# display graphs
x = [0,1]
x_labels = ["Without Test Rules", "With Test Rules"]

if options.create:
    create_data = [friendly_time(create_time), friendly_time(create_time_with_rules)]
    make_graph("Create Speed", x, x_labels, create_data)
    
if options.write:
    write_data = [friendly_time(write_time), friendly_time(write_time_with_rules)]
    make_graph("Write Speed", x, x_labels, write_data)
    
if options.fvg:
    fvg_data = [friendly_time(fvg_time), friendly_time(fvg_time_with_rules)]
    make_graph("Field View Get Speed", x, x_labels, fvg_data)
