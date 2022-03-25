#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import xmlrpclib
import sys
import time
from datetime import datetime
import base64
import os

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('-db', '--database', help='Database used to get the translation file from')
parser.add_argument('-p', '--password', help='Password to connect to the database')
parser.add_argument('-m', '--modules', help="Modules you want to get the untranslated strings from. Each one should be separated by a comma (ie: 'msf_profile,stock_override')", default='')
args = parser.parse_args()

# Config data
if args.database:
    dbname = args.database
else:
    raise Exception('Please use the "-db" option to set the database you want to use')
host = '127.0.0.1'
user = 'admin'
if args.password:
    password = args.password
else:
    raise Exception('Please use the "-p" option to set the password used to connect admin to the database')
xmlrpcport = 8069

# Login
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/common' % (host, xmlrpcport))
uid = sock.login(dbname, user, password)
if not uid:
    print 'Wrong %s password on %s:%s db: %s'% (user, host, xmlrpcport, dbname)
    sys.exit(1)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object' % (host, xmlrpcport))

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
trsl_dir = '../../bin/addons/msf_profile/i18n/'
try:
    trsl_wiz_data = {'lang': 'fr_MF', 'format': 'po', 'advanced': True, 'only_translated_terms': 'n'}
    # Get the modules to translate
    if args.modules:
        module_ids = sock.execute(dbname, uid, password, 'ir.module.module', 'search', [('name', 'in', args.modules.split(','))])
        if module_ids:
            trsl_wiz_data.update({'modules': [(6, 0, module_ids)]})
    trsl_wiz_id = sock.execute(dbname, uid, password, 'base.language.export', 'create', trsl_wiz_data)
    sock.execute(dbname, uid, password, 'base.language.export', 'act_getfile_background', [trsl_wiz_id], {})

    file_data = False
    i = 1
    while i <= 10 and not file_data:
        print 'Waiting for the file... try %s' % (i,)
        time.sleep(30)
        # Get file's data
        file_ids = sock.execute(dbname, uid, password, 'ir.attachment', 'search', [('name', '=', 'fr_MF.po'),('create_date', '>=', now)])
        if file_ids:
            file_data = base64.decodestring(sock.execute(dbname, uid, password, 'ir.attachment', 'read', file_ids[0], ['datas'])['datas'])
            print 'Data retrieved'
        i += 1
    if not file_data:
        print "The translation file could not be retrieved after 300 seconds"
    else:
        # Create the file with the untranslated expressions
        filepath = os.path.join('/tmp/translation', 'fr_MF.po')
        if not os.path.exists('/tmp/translation'):
            os.makedirs('/tmp/translation')
        file = open(filepath, 'w')
        file.write(file_data)
        file.close()
        print 'The new file has been created at "/tmp/translation"'

        # Clean the file and merge it with the translation file
        clean_filepath = os.path.join('/tmp/translation', 'fr_MF_cleaned.po')
        os.system('python clean.py %s > %s' % (filepath, clean_filepath))
        os.system('python merge.py -m %s %s' % (clean_filepath, trsl_dir + 'fr_MF.po'))

        # Rename the old and new files
        os.rename(trsl_dir + 'fr_MF.po', trsl_dir + 'fr_MF_old.po')
        os.rename(trsl_dir + 'fr_MF.po.merged', trsl_dir + 'fr_MF.po')
        print 'The old file has been renamed "%s" and the merged file has been renamed "%s"' % (trsl_dir + 'fr_MF_old.po', trsl_dir + 'fr_MF.po')
except Exception as e:
    raise
    print e
    print '---'
