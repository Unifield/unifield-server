#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import requests
import config

url = f'{config.url}/jsonrpc'
dbname = config.dbname
user = config.user
password = config.password

period = config.period
coordo_instance = config.coordo_code

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

# call export
page = 0
nb_lines = 0
while True:
    page += 1
    r = requests.post(f'{url}/object', json={
        'method': 'execute',
        'params': [
            dbname,
            uid,
            password,
            'waca.export.accounting.lines',
            'export',
            period,
            coordo_instance,
            page
        ]
    }).json().get('result', {})
    if not r['success']:
        print('Error: %s' % r.get('error'))
        sys.exit(1)
    nb_lines += len(r['records'])
    for line in r.get('records', {}):
        print(line)

    if not r['has_next_page']:
        break

print('Total lines:', nb_lines)

