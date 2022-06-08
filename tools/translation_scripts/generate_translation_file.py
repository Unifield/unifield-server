#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import xmlrpc.client
import sys
import time
from datetime import datetime
import base64
import os

import clean
import merge
# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('-rb', '--runbot', help='The host where you want to want to apply the script (Localhost by default)', default='127.0.0.1')
parser.add_argument('-db', '--database', help='Database used to get the translation file from')
parser.add_argument('-p', '--password', help='Password to connect to the database', default='admin')
parser.add_argument('-m', '--modules', help="Modules you want to get the untranslated strings from. Each one should be separated by a comma (ie: 'msf_profile,stock_override')", default='')
parser.add_argument('-l', '--lang', help='Lang code to translate to', default='fr_MF')
args = parser.parse_args()

# Config data
host = args.runbot
if args.database:
    dbname = args.database
elif args.runbot:
    dbname = args.runbot.split('.')[0] + '_HQ1'
else:
    raise Exception('Please use the "-db" option to set the database you want to use')
user = 'admin'
password = args.password
if args.runbot and args.runbot != '127.0.0.1':
    xmlrpcport = 80
else:
    xmlrpcport = 8069

# Login
sock = xmlrpc.client.ServerProxy('http://%s:%s/xmlrpc/common' % (host, xmlrpcport))
uid = sock.login(dbname, user, password)
if not uid:
    print('Wrong %s password on %s:%s db: %s'% (user, host, xmlrpcport, dbname))
    sys.exit(1)
sock = xmlrpc.client.ServerProxy('http://%s:%s/xmlrpc/object' % (host, xmlrpcport))

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
tmp_dir = '/tmp/translation'
scrp_dir = os.path.dirname(os.path.abspath(__file__))
trsl_dir = '/'.join(scrp_dir.split('/')[:-2]) + '/bin/addons/msf_profile/i18n/'
lang = str(args.lang)
try:
    # Look if the researched language in installed
    if not sock.execute(dbname, uid, password, 'res.lang', 'search', [('code', '=', lang), ('active', '=', True), ('translatable', '=', True)]):
        raise Exception("The lang '%s' must exist, be active and translatable to be exported" % (lang,))

    trsl_wiz_data = {'lang': lang, 'format': 'po', 'advanced': True, 'only_translated_terms': 'n'}
    # Get the modules to translate
    if args.modules:
        module_ids = sock.execute(dbname, uid, password, 'ir.module.module', 'search', [('name', 'in', args.modules.split(','))])
        if module_ids:
            trsl_wiz_data.update({'modules': [(6, 0, module_ids)]})
    trsl_wiz_id = sock.execute(dbname, uid, password, 'base.language.export', 'create', trsl_wiz_data)
    sock.execute(dbname, uid, password, 'base.language.export', 'act_getfile_background', [trsl_wiz_id], {})

    file_data = False
    i = 1
    while i <= 60 and not file_data:
        print('Waiting for the file... try %s' % (i,))
        time.sleep(5)
        # Get file's data
        file_ids = sock.execute(dbname, uid, password, 'ir.attachment', 'search', [('name', '=', '%s.po' % (lang,)),('create_date', '>=', now)])
        if file_ids:
            file_data = base64.b64decode(sock.execute(dbname, uid, password, 'ir.attachment', 'read', file_ids[0], ['datas'])['datas'])
            print('Data retrieved')
        i += 1
    if not file_data:
        print("The translation file could not be retrieved after 300 seconds")
    else:
        # Create the file with the untranslated expressions
        filepath = os.path.join(tmp_dir, '%s.po' % (lang,))
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        file = open(filepath, 'w')
        file.write(file_data)
        file.close()
        print('The new file has been created at "/tmp/translation"')

        # Clean the file and merge it with the translation file
        clean_filepath = os.path.join(tmp_dir, '%s_cleaned.po' % (lang,))
        clean.clean(filepath, clean_filepath)
        merge.Merge(clean_filepath, trsl_dir + '%s.po' % (lang,), use_master=True).merge()

        # Rename the old and new files
        os.rename(trsl_dir + '%s.po' % (lang,), trsl_dir + '%s_old.po' % (lang,))
        os.rename(trsl_dir + '%s.po.merged' % (lang,), trsl_dir + '%s.po' % (lang,))
        print('The old file has been renamed "%s" and the merged file has been renamed "%s"' % (trsl_dir + '%s_old.po' % (lang,), trsl_dir + '%s.po' % (lang,)))
except Exception as e:
    raise
    print(e)
    print ('---')
