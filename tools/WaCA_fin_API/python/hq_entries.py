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
        'import_hq_entries',
        [
            {'description': 'Desc', 'reference': 'Ref', 'document_date': '2026-01-30', 'posting_date': '2026-01-30', 'account_code': '60000', 'third_party': '3XTREME LOGISTICS AND SERVICES LIMITED', 'amount': 34.56, 'currency': 'EUR', 'destination': 'TRAI04', 'cost_center': 'NEW03', 'funding_pool': 'PF'},
        ]
    ]
}).json().get('result', {})

print('Result: %s' % r)

# returned value:
# when no error
# {'success': True, 'nb_created': 10, 'nb_updated': 0, 'nb_processed': 2, 'nb_errors': 0}

# in case of errors:
# {
#    'success': False,
#    'nb_errors': 2,
#    'nb_created': 0,
#    'nb_updated': 0,
#    'nb_processed': 3,
#    'error': [
#        {
#            'line': {'description': 'Desc', 'reference': 'Ref', 'document_date': '2026-01-30', 'posting_date': '2026-01-30', 'account_code': '60000', 'third_party': 'toto', 'amount': 34.56, 'currency': 'EUR', 'destination': 'OPS', 'cost_center': 'HT101', 'funding_pool': 'PF'},
#            'error': 'Error: Entry already imported: Desc / Ref / 30/01/2026 (doc) / 30/01/2026 (posting) / 60000 (account) / 34.56 (amount) / toto (3rd party) / HT101 (CC)'
#        }, {
#            'line': {ZZZZ},
#            'error': 'ERROR MSG 2'
#       }
#    ]
#}

