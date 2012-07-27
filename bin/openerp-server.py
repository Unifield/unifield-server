#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

"""
OpenERP - Server
OpenERP is an ERP+CRM program for small and medium businesses.

The whole source code is distributed under the terms of the
GNU Public Licence.

(c) 2003-TODAY, Fabien Pinckaers - OpenERP s.a.
"""

import os
import sys
import psycopg2
from datetime import datetime

## Unix-like find
def find(path):
    files = os.listdir(path)
    for name in iter(files):
        abspath = path+os.path.sep+name
        if os.path.isdir( abspath ) and not os.path.islink( abspath ):
            files.extend( map(lambda x:name+os.path.sep+x, os.listdir(abspath)) )
    return files

## Try...Resume...
def Try(command):
    try:
        command()
    except:
        e, msg = sys.exc_info()[0].__name__, str(sys.exc_info()[1])
        print str(msg)
        return False
    else:
        return True

def rmFR(files, path=None, verbose=False):
    if path is None and isinstance(files, str):
        path, files = files, find(files)
    for f in reversed(files):
        target = os.path.join(path, f) if path is not None else f
        if os.path.isfile(target) or os.path.islink(target):
            print "unlink", target
            os.unlink( target )
        elif os.path.isdir(target):
            print "rmdir", target
            os.rmdir( target )

## We expect to be in the bin/ directory to proceed
if os.path.exists('update.lock'):
    rev_file = os.path.join('.update','revisions.txt')
    hist_file = "revision_history.txt"
    infos = None
    revisions = None
    cur = None
    conn = None
    update_revisions = None
    files = None
    args = list(sys.argv)
    for i, x in enumerate(args):
        if x in ('-d', '-u'):
            args[i] = None
            args[i+1] = None
    args = filter(lambda x:x is not None, args)
    try:
        ## Read DB name
        f = open('update.lock')
        infos = eval(f.read())
        f.close()
        revisions = ",".join( map(lambda x:"'"+str(x)+"'", infos['revisions']) )
        ## Connect to the DB
        conn = psycopg2.connect(database=infos['dbname'], user=infos['db_user'], password=infos['db_password'], host=infos['db_host'], port=infos['db_port'])
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        ## Explore .update directory
        files = find('.update')
        ## Prepare backup directory
        if not os.path.exists('backup'):
            os.mkdir('backup')
        else:
            rmFR('backup')
        ## Update Files
        print "Updating..."
        for f in files:
            target = os.path.join('.update', f)
            bak = os.path.join('backup', f)
            if os.path.isdir(target):
                if os.path.isfile(f) or os.path.islink(f):
                    os.unlink(f)
                if not os.path.exists(f):
                    os.mkdir(f)
                os.mkdir(bak)
            else:
                if os.path.exists(f):
                    print "`%s' -> `%s'" % (f, bak)
                    os.rename(f, bak)
                print "`%s' -> `%s'" % (target, f)
                os.rename(target, f)
        ## Update installed revisions in DB
        cur.execute("""UPDATE sync_client_version SET state = 'installed', applied = '%s' WHERE name in (%s)"""
            % ( datetime.today().strftime("%Y-%m-%d %H:%M:%S"), revisions ))
        print "Update successful."
        print "Revisions added: ", ", ".join( infos['revisions'] )
        args.extend(['-d', infos['dbname'], '-u', 'all'])
    except:
        print 'failure!'
        ## Update DB to mark revisions as not-installed
        if cur and infos:
            Try(lambda:cur.execute("""UPDATE sync_client_version SET state = 'not-installed' WHERE name in (%s)"""
                % ( revisions )))
        ## Restore backup and purge .update
        if files:
            print "Restoring..."
            for f in reversed(files):
                target = os.path.join('backup', f)
                if os.path.isfile(target) or os.path.islink(target):
                    print "`%s' -> `%s'" % (target, f)
                elif os.path.isdir(target):
                    print "rmdir", target
                    os.rmdir( target )
            print "Purging..."
            Try(lambda:rmFR(files, '.update'))
            print "rmdir", '.update'
            Try(lambda:os.rmdir( '.update' ))
    finally:
        if cur: cur.close()
        if conn: conn.close()
    ## Remove lock file
    print "rm", 'update.lock'
    Try(lambda:os.unlink( 'update.lock' ))
    print "Restart OpenERP in", infos['exec_path'], "with: ", list(sys.argv) + args
    if infos: os.chdir(infos['exec_path'])
    os.execv(sys.executable, [sys.executable] + args)

print "OpenERP Started with:", sys.argv
print "Executable:", sys.executable

#----------------------------------------------------------
# python imports
#----------------------------------------------------------
import logging
import signal
import threading
import traceback

import release
__author__ = release.author
__version__ = release.version

if os.name == 'posix':
    import pwd
    # We DON't log this using the standard logger, because we might mess
    # with the logfile's permissions. Just do a quick exit here.
    if pwd.getpwuid(os.getuid())[0] == 'root' :
        sys.stderr.write("Attempted to run OpenERP server as root. This is not good, aborting.\n")
        sys.exit(1)

#----------------------------------------------------------
# get logger
#----------------------------------------------------------
import netsvc
logger = logging.getLogger('server')

#-----------------------------------------------------------------------
# import the tools module so that the commandline parameters are parsed
#-----------------------------------------------------------------------
import tools
logger.info("OpenERP version - %s", release.version)
for name, value in [('addons_path', tools.config['addons_path']),
                    ('database hostname', tools.config['db_host'] or 'localhost'),
                    ('database port', tools.config['db_port'] or '5432'),
                    ('database user', tools.config['db_user'])]:
    logger.info("%s - %s", name, value)

# Don't allow if the connection to PostgreSQL done by postgres user
#if tools.config['db_user'] == 'postgres':
#    logger.error("Connecting to the database as 'postgres' user is forbidden, as it present major security issues. Shutting down.")
#    sys.exit(1)

import time

#----------------------------------------------------------
# init net service
#----------------------------------------------------------
logger.info('initialising distributed objects services')

#---------------------------------------------------------------
# connect to the database and initialize it with base if needed
#---------------------------------------------------------------
import pooler

#----------------------------------------------------------
# import basic modules
#----------------------------------------------------------
import osv
import workflow
import report
import service

#----------------------------------------------------------
# import addons
#----------------------------------------------------------

import addons

#----------------------------------------------------------
# Load and update databases if requested
#----------------------------------------------------------

import service.http_server

if not ( tools.config["stop_after_init"] or \
    tools.config["translate_in"] or \
    tools.config["translate_out"] ):
    service.http_server.init_servers()
    service.http_server.init_xmlrpc()
    service.http_server.init_static_http()

    import service.netrpc_server
    service.netrpc_server.init_servers()

if tools.config['db_name']:
    for dbname in tools.config['db_name'].split(','):
        db,pool = pooler.get_db_and_pool(dbname, update_module=tools.config['init'] or tools.config['update'], pooljobs=False)
        cr = db.cursor()

        if tools.config["test_file"]:
            logger.info('loading test file %s', tools.config["test_file"])
            tools.convert_yaml_import(cr, 'base', file(tools.config["test_file"]), {}, 'test', True)
            cr.rollback()

        pool.get('ir.cron')._poolJobs(db.dbname)

        cr.close()

#----------------------------------------------------------
# translation stuff
#----------------------------------------------------------
if tools.config["translate_out"]:
    import csv

    if tools.config["language"]:
        msg = "language %s" % (tools.config["language"],)
    else:
        msg = "new language"
    logger.info('writing translation file for %s to %s', msg, tools.config["translate_out"])

    fileformat = os.path.splitext(tools.config["translate_out"])[-1][1:].lower()
    buf = file(tools.config["translate_out"], "w")
    dbname = tools.config['db_name']
    cr = pooler.get_db(dbname).cursor()
    tools.trans_export(tools.config["language"], tools.config["translate_modules"] or ["all"], buf, fileformat, cr)
    cr.close()
    buf.close()

    logger.info('translation file written successfully')
    sys.exit(0)

if tools.config["translate_in"]:
    context = {'overwrite': tools.config["overwrite_existing_translations"]}
    dbname = tools.config['db_name']
    cr = pooler.get_db(dbname).cursor()
    tools.trans_load(cr,
                     tools.config["translate_in"], 
                     tools.config["language"],
                     context=context)
    tools.trans_update_res_ids(cr)
    cr.commit()
    cr.close()
    sys.exit(0)

#----------------------------------------------------------------------------------
# if we don't want the server to continue to run after initialization, we quit here
#----------------------------------------------------------------------------------
if tools.config["stop_after_init"]:
    sys.exit(0)


#----------------------------------------------------------
# Launch Servers
#----------------------------------------------------------

LST_SIGNALS = ['SIGINT', 'SIGTERM']

SIGNALS = dict(
    [(getattr(signal, sign), sign) for sign in LST_SIGNALS]
)

netsvc.quit_signals_received = 0

def handler(signum, frame):
    """
    :param signum: the signal number
    :param frame: the interrupted stack frame or None
    """
    netsvc.quit_signals_received += 1
    if netsvc.quit_signals_received > 1:
        sys.stderr.write("Forced shutdown.\n")
        os._exit(0)

def dumpstacks(signum, frame):
    # code from http://stackoverflow.com/questions/132058/getting-stack-trace-from-a-running-python-application#answer-2569696
    # modified for python 2.5 compatibility
    thread_map = dict(threading._active, **threading._limbo)
    id2name = dict([(threadId, thread.getName()) for threadId, thread in thread_map.items()])
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# Thread: %s(%d)" % (id2name[threadId], threadId))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                code.append("  %s" % (line.strip()))
    logging.getLogger('dumpstacks').info("\n".join(code))

for signum in SIGNALS:
    signal.signal(signum, handler)

if os.name == 'posix':
    signal.signal(signal.SIGQUIT, dumpstacks)

def quit(restart=False):
    netsvc.Agent.quit()
    netsvc.Server.quitAll()
    if tools.config['pidfile']:
        os.unlink(tools.config['pidfile'])
    logger = logging.getLogger('shutdown')
    logger.info("Initiating OpenERP Server shutdown")
    logger.info("Hit CTRL-C again or send a second signal to immediately terminate the server...")
    logging.shutdown()

    # manually join() all threads before calling sys.exit() to allow a second signal
    # to trigger _force_quit() in case some non-daemon threads won't exit cleanly.
    # threading.Thread.join() should not mask signals (at least in python 2.5)
    for thread in threading.enumerate():
        if thread != threading.currentThread() and not thread.isDaemon():
            while thread.isAlive():
                # need a busyloop here as thread.join() masks signals
                # and would present the forced shutdown
                thread.join(0.05)
                time.sleep(0.05)
                time.sleep(1)
                if os.name == 'nt':
                    try:
                        logger.info("Killing", thread.getName())
                        thread._Thread__stop()
                    except:
                        logger.info(str(thread.getName()) + ' could not be terminated')
    if not restart:
        sys.exit(0)
    else:
	os.execv(sys.executable, [sys.executable] + sys.argv)

if tools.config['pidfile']:
    fd = open(tools.config['pidfile'], 'w')
    pidtext = "%d" % (os.getpid())
    fd.write(pidtext)
    fd.close()

netsvc.Server.startAll()

logger.info('OpenERP server is running, waiting for connections...')

tools.restart_required = False

while netsvc.quit_signals_received == 0 and not tools.restart_required:
    time.sleep(5)

quit(restart=tools.restart_required)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
