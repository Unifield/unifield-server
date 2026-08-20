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
        'import_currencies',
        [
            {'code': 'AED' , 'name_en': 'UNITED ARAB EMIRATES DIRHAM' , 'name_fr': 'UNITED ARAB EMIRATES DIRHAM'},
            {'code': 'CHF' , 'name_en': 'SWISS FRANC' , 'name_fr': 'FRANC SUISSE'},
        ]
    ]
}).json().get('result', {})

print('Result: %s' % r)

# returned value:
# when no error
# {'success': True, 'nb_created': 0, 'nb_updated': 0, 'nb_processed': 2, 'nb_errors': 0}

# in case of errors:
# {'success': False, 'nb_errors': 1, 'nb_created': 1, 'nb_updated': 0, 'nb_processed': 2, 'error': [{'line': {'code': 'AED', 'name_en': 'UNITED ARAB EMIRATES DIRHAM'}, 'error': 'Error: "name_fr" cannot be empty'}]}

