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
import sys
sys.path.append('.')
import updater
updater.do_update()

#----------------------------------------------------------
# python imports
#----------------------------------------------------------
import logging
import os
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

# Log an operations.event. In the contexts we are called, we don't
# have a open cr. We need to look in pooler.pool_dic to find the
# list of DBs that have already been opened and upgraded.
# We ignore all errors because logging events is best
# effort.
def ops_event(what, dbname=None):
    for db in list(pooler.pool_dic.keys()):
        cr = None
        if dbname is not None and db != dbname:
            continue
        try:
            c, pool = pooler.get_db_and_pool(db, upgrade_modules=False)
            cr = c.cursor()
            oe = pool.get('operations.event')
            if oe:
                oe.create(cr, 1, { 'kind': what })
            cr.commit()
        except:
            pass
        finally:
            if cr is not None:
                cr.close()
                cr = None

#-----------------------------------------------------------------------
# import the tools module so that the commandline parameters are parsed
#-----------------------------------------------------------------------
import tools
updater.update_path()
logger.info("OpenERP version - %s", release.version)
logger.info("sys.path %s", ' '.join(sys.path))
for name, value in [('addons_path', tools.config['addons_path']),
                    ('database hostname', tools.config['db_host'] or 'localhost'),
                    ('database port', tools.config['db_port'] or '5432'),
                    ('database user', tools.config['db_user'])]:
    logger.info("%s - %s", name, value)
updater.do_pg_update()

# Don't allow if the connection to PostgreSQL done by postgres user
if tools.config['db_user'] == 'postgres':
    logger.error("Connecting to the database as 'postgres' user is forbidden, as it present major security issues. Shutting down.")
    sys.exit(1)

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
# (the asserts are to silence pyflakes warnings)
#----------------------------------------------------------
import osv; assert osv
import workflow; assert workflow
import report; assert report
import service; assert service

#----------------------------------------------------------
# import addons
#----------------------------------------------------------
import addons; assert addons

#----------------------------------------------------------
# Load and update databases if requested
#----------------------------------------------------------

from service import http_server
import updater

if not ( tools.config["stop_after_init"] or \
         tools.config["translate_in"] or \
         tools.config["translate_out"] ):
    http_server.init_servers()
    http_server.init_xmlrpc()
    http_server.init_jsonrpc()
    http_server.init_static_http()

    from service import netrpc_server
    netrpc_server.init_servers()

if tools.config['db_name']:
    for dbname in tools.config['db_name'].split(','):
        ops_event('commandline-update', dbname)
        cr = False
        try:
            db,pool = pooler.get_db_and_pool(dbname, update_module=tools.config['init'] or tools.config['update'], pooljobs=False)
            cr = db.cursor()

            try:
                if tools.config["test_file"]:
                    logger.info('loading test file %s', tools.config["test_file"])
                    tools.convert_yaml_import(cr, 'base', open(tools.config["test_file"]), {}, 'test', True)
                    cr.rollback()
                pool.get('ir.cron').restart(db.dbname)
            finally:
                if cr:
                    cr.close()

        except Exception as e:
            logger.error('Unable to load %s: %s', dbname, e)
            try:
                tools.config.delete_db_name(dbname)
            except Exception as e:
                logger.error('unable to remove %s from %s, error: %s', dbname, tools.config.rcfile, e)
            if cr:
                cr.close()

#----------------------------------------------------------
# translation stuff
#----------------------------------------------------------
if tools.config["translate_out"]:
    if tools.config["language"]:
        msg = "language %s" % (tools.config["language"],)
    else:
        msg = "new language"
    logger.info('writing translation file for %s to %s', msg, tools.config["translate_out"])

    fileformat = os.path.splitext(tools.config["translate_out"])[-1][1:].lower()
    buf = open(tools.config["translate_out"], "w")
    dbname = tools.config['db_name']
    cr = pooler.get_db(dbname).cursor()
    try:
        tools.trans_export(tools.config["language"], tools.config["translate_modules"] or ["all"], buf, fileformat, cr)
    finally:
        cr.close()
        buf.close()

    logger.info('translation file written successfully')
    sys.exit(0)

if tools.config["translate_in"]:
    context = {'overwrite': tools.config["overwrite_existing_translations"]}
    dbname = tools.config['db_name']
    cr = pooler.get_db(dbname).cursor()
    try:
        tools.trans_load(cr,
                         tools.config["translate_in"],
                         tools.config["language"],
                         context=context)
        tools.trans_update_res_ids(cr)
    finally:
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
    id2name = dict([(threadId, thread.getName()) for threadId, thread in list(thread_map.items())])
    code = []
    for threadId, stack in list(sys._current_frames().items()):
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

def quit(restart=False, db_name=''):
    if restart:
        time.sleep(updater.restart_delay)
    netsvc.Agent.quit()
    netsvc.Server.quitAll()
    if tools.config['pidfile']:
        os.unlink(tools.config['pidfile'])
    logger = logging.getLogger('shutdown')
    logger.info("Initiating OpenERP Server shutdown")
    logger.info("Hit CTRL-C again or send a second signal to immediately terminate the server...")

    ops_event('shutdown')
    logging.shutdown()
    stop_time = time.time()
    # manually join() all threads before calling sys.exit() to allow a second signal
    # to trigger _force_quit() in case some non-daemon threads won't exit cleanly.
    # threading.Thread.join() should not mask signals (at least in python 2.5)
    running_thread = False
    for thread in threading.enumerate():
        if thread != threading.current_thread() and not thread.daemon:
            while thread.is_alive():
                if time.time() - stop_time > 1:
                    running_thread = True
                    break
                else:
                    # need a busyloop here as thread.join() masks signals
                    # and would present the forced shutdown
                    thread.join(0.05)
                    time.sleep(0.05)

    if not restart:
        if running_thread:
            os._exit(0)
        sys.exit(0)
    elif os.name == 'nt':
        if running_thread:
            os._exit(1)
        sys.exit(1)
    else:
        os.execv(sys.executable, [sys.executable] + sys.argv)

#-----------------------------------------------------------
# manage some platform specific behaviour
#-----------------------------------------------------------

if sys.platform == 'win32':
    import win32api
    def mainthread_sleep(stime):
        # use SleepEx so the process can recieve console control event
        # (required to Windows service survive if the user logout)
        win32api.SleepEx(stime*1000)
else:
    def mainthread_sleep(stime):
        time.sleep(stime)

if tools.config['pidfile']:
    fd = open(tools.config['pidfile'], 'w')
    pidtext = "%d" % (os.getpid())
    fd.write(pidtext)
    fd.close()

netsvc.Server.startAll()

updater.check_mako_xml()
updater.reconnect_sync_server()
logger.info('OpenERP server is running, waiting for connections...')

while netsvc.quit_signals_received == 0 and not updater.restart_required:
    mainthread_sleep(5),

quit(restart=updater.restart_required)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
