#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import requests
import csv
import config

url = f'{config.url}/jsonrpc'
dbname = config.dbname
user = config.user
password = config.password
api_key = config.api_key

#object_to_pull = 'hr.employee'
object_to_pull = 'res.partner'
#object_to_pull = 'account.journal

# login
r = requests.post(f'{url}/common', json={
    'method': 'login',
    'params': [
        dbname,
        user,
        password
    ]
})
uid = r.json().get('result')
if not uid:
    print('Wrong %s password on %s db: %s'% (user, url, dbname))
    sys.exit(1)

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

r = requests.post(f'{url}/object', json={
    'method': 'execute',
    'params': [
        dbname,
        uid,
        password,
        'waca.fin.sync',
        'generate_session',
        object_to_pull,
        api_key,
        False
    ]
})
session_d = r.json().get('result', {})
if not session_d['success']:
    print('New session error: %s' % session_d.get('error'))
    sys.exit(1)
session = session_d.get('session')

csv_f = False
f = False
if len(sys.argv) > 1:
    print(f'Export to file: {sys.argv[1]}')
    f = open(sys.argv[1], 'w')
    csv_f = csv.writer(f)

page = 1
line = 0
while True:
    # get the records page by page, limited to 200 records
    ret = requests.post(f'{url}/object', json={
        'method': 'execute',
        'params': [
            dbname,
            uid,
            password,
            'waca.fin.sync',
            'get_record',
            session,
            page
        ]
    }).json().get('result', {})

    if not ret['success']:
        # success: boolean
        # error: string
        print('Error %s' % ret.get('error'))
        sys.exit(1)

    for record in ret.get('records'):
        if f:
            if not line:
                keys = record.keys()
                csv_f.writerow(keys)
            csv_f.writerow([record.get(x) for x in keys])
        else:
            print(record)
        line += 1
    if not ret['has_next_page']:
        # has_next_page is a boolean
        # if no new page stop the loop
        break
    page += 1

if f:
    f.close()
# confirm the session, next call with the same "client key" will be incremental
# if the session is not confirmed, UniField considers it as not committed and will send again the data on the next API call
ret = requests.post(f'{url}/object', json={
    'method': 'execute',
    'params': [
        dbname,
        uid,
        password,
        'waca.fin.sync',
        'confirm_session',
        session,
    ]
}).json().get('result', {})
if not ret['success']:
    print('Error %s' % ret.get('error'))
