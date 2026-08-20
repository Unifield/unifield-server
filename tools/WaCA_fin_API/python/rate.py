#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import requests
import config

url = f'{config.url}/jsonrpc'
dbname = config.dbname
user = config.user
password = config.password

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

r = requests.post(f'{url}/object', json={
    'method': 'execute',
    'params': [
        dbname,
        uid,
        password,
        'waca.fin.sync',
        'import_rates',
        [
            {'currency': 'CHF', 'date': '2026-12-01', 'rate': 4.46},
            {'currency': 'AED', 'date': '2026-12-01', 'rate': 3.456789}
        ]
    ]
}).json().get('result', {})

print('Result: %s' % r)

# returned value:
# when no error
# {'success': True, 'nb_created': 0, 'nb_updated': 0, 'nb_processed': 2, 'nb_errors': 0}

# in case of errors:
# {
#    'success': False,
#    'nb_errors': 2,
#    'nb_created': 0,
#    'nb_updated': 0,
#    'nb_processed': 3,
#    'error': [
#        {
#            'line': {'currency': 'CHFT', 'date': '2026-12-01', 'rate': 4.44},
#            'error': 'Error: "currency" CHFT does not exist'
#        }, {
#            'line': {'currency': 'ABCD1', 'date': '2026-12-01', 'rate': 1.123456},
#            'error': 'Error: "currency" ABCD1 does not exist'}
#    ]
#}

