# -*- coding: utf-8 -*-

import sys
import requests
import csv
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


def export_to_file(object, method, args, page, file_name):

    f = open(file_name, 'w')
    csv_f = csv.writer(f, quotechar='"', delimiter=',')
    nb_line = 0
    while True:
        params = [
            dbname,
            uid,
            password,
            object,
            method,
        ] + args
        if page:
            params.append(page)

        r = requests.post(f'{url}/object', json={
            'method': 'execute',
            'params': params,
        }).json().get('result', {})
        if not r['success']:
            print(f"{object} {method} error: {r.get('error')}")
            sys.exit(1)

        for line in r.get('records', {}):
            if nb_line == 0:
                keys = line.keys()
                csv_f.writerow(keys)
            nb_line += 1
            csv_f.writerow([line[k] for k in keys])

        if not r['has_next_page']:
            break

        page += 1

    f.close()

    print(f"{object} {method} {nb_line} records to {file_name}")

r = requests.post(f'{url}/object', json={
    'method': 'execute',
    'params': [
        dbname,
        uid,
        password,
        'waca.export.accounting.lines',
        'ready_to_export'
    ],
}).json().get('result', {})

if not r['success']:
    print(f"ready_to_export error: {r.get('error')}")
    sys.exit(1)

for row in r.get('records', {}):
    period = row['period']
    instance = row['instance']
    export_to_file('waca.export.accounting.lines', 'export', [period, instance], 1, f'{period}_{instance}_accounting_entries.csv')
    export_to_file('waca.export.accounting.lines', 'matching_report', [period, instance], 1, f'{period}_{instance}_matching_report.csv')
    export_to_file('waca.export.balances', 'export', [period, instance], 1, f'{period}_{instance}_balances.csv')

