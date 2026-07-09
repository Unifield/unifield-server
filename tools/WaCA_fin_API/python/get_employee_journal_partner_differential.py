#!/usr/bin/env python
# -*- coding: utf-8 -*-

import xmlrpc.client
import sys
import config

url = config.url
dbname = config.dbname
user = config.user
password = config.password
api_key = config.api_key


# login
print('%s/xmlrpc/common' % (url, ))
sock = xmlrpc.client.ServerProxy('%s/xmlrpc/common' % (url,))
uid = sock.login(dbname, user, password)
if not uid:
    print('Wrong %s password on %s db: %s'% (user, url, dbname))
    sys.exit(1)

sock = xmlrpc.client.ServerProxy('%s/xmlrpc/object' % (url, ))


# create a sync session
# arguments:
#    'waca.fin.sync': object used to manage the session
#    'generate_session': string, method to call
#    object_to_pull: string, object to retrieve, currently only 'res.partner' is allowed
#    'ocp_test': string, client key, any string, to distinguish tests from production,
#       the next call with the same client key will send the differences since the last confirmed session
#    full_sync: boolean, True to retrieve all data, False to retrieve only the differences, default value: False
#
# returned values:
#     success: boolean
#     error: if success is False, error message
#     session: string, session identifier

object_to_pull = 'hr.employee'
#object_to_pull = 'res.partner'
#object_to_pull = 'account.journal'
session_d = sock.execute(dbname, uid, password, 'waca.fin.sync', 'generate_session', object_to_pull, api_key, False)

if not session_d['success']:
    print('New session error: %s' % session_d.get('error'))
    sys.exit(1)

# get the session name
session = session_d.get('session')

page = 1
while True:
    # get the records page by page, limited to 200 records
    ret = sock.execute(dbname, uid, password, 'waca.fin.sync', 'get_record', session, page)

    if not ret['success']:
        # success: boolean
        # error: string
        print('Error %s' % ret.get('error'))
        sys.exit(1)

    for record in ret.get('records'):
        print(record)

    if not ret['has_next_page']:
        # has_next_page is a boolean
        # if no new page stop the loop
        break
    page += 1

# confirm the session, next call with the same "client key" will be incremental
# if the session is not confirmed, UniField considers it as not committed and will send again the data on the next API call
ret = sock.execute(dbname, uid, password, 'waca.fin.sync', 'confirm_session', session)
if not ret['success']:
    print('Error %s' % ret.get('error'))
