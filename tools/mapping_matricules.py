import csv

import xmlrpc.client
import sys


host = '127.0.0.1'
xmlrpcport = 20863
dbname='jfb-dev-us-12472_prod_OCP_HQ_20240907_0444'
proto='http'
user='admin'
password = 'XXX'

# login
sock = xmlrpc.client.ServerProxy('%s://%s:%s/xmlrpc/common' % (proto, host, xmlrpcport))
uid = sock.login(dbname, user, password)
if not uid:
    print('Wrong %s password on %s:%s db: %s'% (user, host, xmlrpcport, dbname))
    sys.exit(1)

sock = xmlrpc.client.ServerProxy('%s://%s:%s/xmlrpc/object' % (proto, host, xmlrpcport))
f = open('mapping.csv', 'r', newline='')

csvf = csv.reader(f)
next(csvf)
line_nb = 2
for line in csvf:
    sock.execute(dbname, uid, password, 'ocp.employee.mapping', 'create', {'arcole': line[3], 'workday': line[4], 'section_code': line[5] or False})
    if line[1] == 'VOL':
        continue
    exp_ids = sock.execute(dbname, uid, password, 'hr.employee', 'search', [('employee_type', '=', 'ex'), ('active', 'in', ['t', 'f']), ('identification_id', '=', line[3])])
    if len(exp_ids) == 1:
        try:
            sock.execute(dbname, uid, password, 'hr.employee', 'write', exp_ids, {'identification_id': line[4], 'section_code': line[5] or False, 'former_identification_id': line[3]})
        except Exception as e:
            print(e)
            print(line_nb, line)
    line_nb += 1


