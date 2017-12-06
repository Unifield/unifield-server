#!/usr/bin/env python

import sys
import os
import psycopg2
import ConfigParser
import argparse

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-c", "--config", metavar="rcfile", help="OpenERP config file")
parser.add_argument("-r", "--db_user", metavar="db_user", help="specify the database user name")
parser.add_argument("-w", "--db_password", metavar="db_password", help="specify the database password")
parser.add_argument('--db_host', metavar='db_host', help='specify the database host')
parser.add_argument('--db_port', metavar='db_port', help='specify the database port', type=int, default=os.environ.get('PGPORT', 5432))
parser.add_argument('-y',  help='do not ask confirmation', action="store_true", default=False)
parser.add_argument("dbs_name", help="comma separated list of dbs to fix")
o = parser.parse_args()

dsn = ''
if o.config:
    p = ConfigParser.ConfigParser()
    p.read([o.config])
    o.db_password = dict(p.items('options'))['db_password']
    o.db_user = dict(p.items('options'))['db_user']
    o.db_host = dict(p.items('options'))['db_host']
    o.db_port = dict(p.items('options'))['db_port']

for arg in ['password', 'user', 'host', 'port']:
    attr = getattr(o, 'db_%s' % arg)
    if attr and attr != 'False':
        dsn += ' %s=%s ' % (arg, attr)

ret = ''
if o.y:
    ret = 'y'
while ret.lower() not in ('y','n'):
    ret = raw_input("This is a dev tool, DO NOT USE ON PRODUCTION, I'll fix dbs: %s [y/n] " % (o.dbs_name, ))

if ret.lower() == 'n':
    print "Nothing done"
    sys.exit(0)

exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(exe_dir,"../bin"))
import updater
unifield_version = os.path.join(exe_dir, '../bin/unifield-version.txt')

versions = updater.parse_version_file(unifield_version)
for db_name in o.dbs_name.split(','):
    try:
        client_dsn = '%s dbname=%s'%(dsn, db_name)
        db = psycopg2.connect(client_dsn)
        cr = db.cursor()
        cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname='sync_server_version'")
        sync_server = cr.rowcount

        if sync_server:
            cr.execute('delete from sync_server_version')
        else:
            cr.execute('delete from sync_client_version')

        for version in versions:
            if sync_server:
                cr.execute("insert into sync_server_version (name, sum, state, date) values (%s, %s, 'confirmed', %s)", (version['name'], version['md5sum'], version['date']))
            else:
                cr.execute("insert into sync_client_version (name, sum, state, date, applied) values (%s, %s, 'installed', %s, %s)", (version['name'], version['md5sum'], version['date'], version['date']))

        db.commit()
        print "%s fixed" % (db_name, )
    except Exception, e:
        print "Can't fix %s, %s" % (db_name, e)


