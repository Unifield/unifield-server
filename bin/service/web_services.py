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

import base64
import os
from . import security
import _thread
import threading
import time
import sys
import platform
import addons
import ir
import netsvc
import pooler
import release
import sql_db
import tools
import locale
import logging
import datetime
import csv
import re
from osv import osv
from tools.translate import _
from io import StringIO
from tempfile import NamedTemporaryFile
from updater import get_server_version
from tools.misc import file_open
from mako.template import Template
from mako import exceptions
from mako.runtime import Context
import codecs
from passlib.hash import bcrypt
from report import report_sxw
from functools import reduce

def _check_db_name(name):
    '''Raise if the name is composed with unauthorized characters
    '''
    if name and isinstance(name, str):
        # allow char, number, _ and -
        if not re.match('^[a-zA-Z][a-zA-Z0-9_-]+$', name):
            raise Exception(_("You must avoid all accents, space or special characters."))

def export_csv(fields, result, result_file_path):
    try:
        with open(result_file_path, 'w') as result_file:
            writer = csv.writer(result_file, quoting=csv.QUOTE_ALL)
            writer.writerow(fields)
            for data in result:
                row = []
                for d in data:
                    if isinstance(d, str):
                        d = d.replace('\n',' ').replace('\t',' ')
                    if d is False:
                        d = None
                    row.append(d)
                writer.writerow(row)
    except IOError as xxx_todo_changeme:
        (errno, strerror) = xxx_todo_changeme.args
        raise Exception(_("Operation failed\nI/O error")+"(%s)" % (errno,))

def check_tz():
    db = sql_db.db_connect('template1')
    cr = db.cursor()
    try:
        cr.execute('select now() - %s', (datetime.datetime.now(),))
        now = cr.fetchone()[0]
        if abs(now) >= datetime.timedelta(minutes=10):
            return _('Time zones of UniField server and PostgreSQL server differ. Please check the computer configuration.')
    finally:
        cr.close()
    return ''


class db(netsvc.ExportService):
    def __init__(self, name="db"):
        netsvc.ExportService.__init__(self, name)
        self.joinGroup("web-services")
        self.actions = {}
        self.id = 0
        self.id_protect = threading.Semaphore()

    def dispatch(self, method, auth, params):
        if method == 'drop':
            passwd = params[0]
            params = params[1:]
            security.check_super_dropdb(passwd)
        elif method in ('dump', 'dump_file'):
            passwd = params[0]
            params = params[1:]
            security.check_super_bkpdb(passwd)
        elif method in ('restore', 'restore_file'):
            passwd = params[0]
            params = params[1:]
            security.check_super_restoredb(passwd)
        elif method in [ 'create', 'get_progress', 'rename',
                         'change_admin_password', 'migrate_databases',
                         'instance_auto_creation']:
            passwd = params[0]
            params = params[1:]
            security.check_super(passwd)
        elif method in [ 'db_exist', 'list', 'list_lang', 'server_version',
                         'check_timezone', 'connected_to_prod_sync_server',
                         'check_super_password_validity', 'check_password_validity',
                         'creation_get_resume_progress']:
            # params = params
            # No security check for these methods
            pass
        else:
            raise KeyError("Method not found: %s" % method)
        fn = getattr(self, 'exp_'+method)
        return fn(*params)

    def new_dispatch(self,method,auth,params):
        pass

    def _create_empty_database(self, name):
        db = sql_db.db_connect('template1')
        cr = db.cursor()
        try:
            cr.autocommit(True) # avoid transaction block
            _check_db_name(name)
            cr.execute("""CREATE DATABASE "%s" ENCODING 'unicode' TEMPLATE "template0" """ % name)  # ignore_sql_check
        finally:
            cr.close(True)

    def exp_create(self, db_name, demo, lang, user_password='admin'):
        _check_db_name(db_name)
        self.id_protect.acquire()
        self.id += 1
        id = self.id
        self.id_protect.release()
        self.actions[id] = {'clean': False}
        self._create_empty_database(db_name)

        # encrypt the db admin password
        user_password = bcrypt.encrypt(tools.ustr(user_password))

        class DBInitialize(object):
            def __call__(self, serv, id, db_name, demo, lang, user_password='admin'):
                cr = None
                try:
                    serv.actions[id]['progress'] = 0
                    cr = sql_db.db_connect(db_name).cursor()
                    tools.init_db(cr)
                    tools.config['lang'] = lang
                    cr.commit()
                    cr.close(True)
                    cr = None
                    pool = pooler.restart_pool(db_name, demo, serv.actions[id],
                                               update_module=True)[1]

                    cr = sql_db.db_connect(db_name).cursor()

                    if lang:
                        modobj = pool.get('ir.module.module')
                        mids = modobj.search(cr, 1, [('state', '=', 'installed')])
                        modobj.update_translations(cr, 1, mids, lang)

                    cr.execute('UPDATE res_users SET password=%s, context_lang=%s, active=True WHERE login=%s RETURNING id', (
                        user_password, lang, 'admin'))
                    uid = cr.fetchone()[0]
                    cr.execute('SELECT login, password, name ' \
                               '  FROM res_users ' \
                               ' ORDER BY login')
                    serv.actions[id]['users'] = cr.dictfetchall()

                    # add the extended interface group to the admin user
                    # this is needed to be able to install other modules
                    res_group_obj = pool.get('res.groups')
                    group_extended_id = res_group_obj.get_extended_interface_group(cr, 1)
                    if group_extended_id:
                        res_users_obj = pool.get('res.users')
                        res_users_obj.write(cr, uid, uid, {'groups_id': [(4, group_extended_id)]})
                    serv.actions[id]['clean'] = True
                    cr.commit()
                except Exception as e:
                    serv.actions[id]['clean'] = False
                    serv.actions[id]['exception'] = e
                    import traceback
                    e_str = StringIO()
                    traceback.print_exc(file=e_str)
                    traceback_str = e_str.getvalue()
                    e_str.close()
                    netsvc.Logger().notifyChannel('web-services', netsvc.LOG_ERROR, 'CREATE DATABASE\n%s' % (traceback_str))
                    serv.actions[id]['traceback'] = traceback_str
                finally:
                    if cr:
                        cr.close(True)
        logger = netsvc.Logger()
        logger.notifyChannel("web-services", netsvc.LOG_INFO, 'CREATE DATABASE: %s' % (db_name.lower()))
        dbi = DBInitialize()
        create_thread = threading.Thread(target=dbi,
                                         args=(self, id, db_name, demo, lang, user_password))
        create_thread.start()
        self.actions[id]['thread'] = create_thread
        return id

    def exp_instance_auto_creation(self, db_name):
        db, pool = pooler.get_db_and_pool(db_name)
        cr = db.cursor()

        creation_obj = pool.get('instance.auto.creation')
        existing_auto_creation = creation_obj.search(cr, 1, [('dbname', '=', cr.dbname)])
        if existing_auto_creation:
            creation_id = existing_auto_creation[0]
        else:
            creation_id = creation_obj.create(cr, 1, {'dbname': cr.dbname})

        create_thread = threading.Thread(target=creation_obj.background_install,
                                         args=(cr, pool, 1, creation_id))
        create_thread.start()
        create_thread.join(1)
        return True

    def exp_creation_get_resume_progress(self, db_name):
        db, pool = pooler.get_db_and_pool(db_name)
        cr = db.cursor()
        try:
            creation_obj = pool.get('instance.auto.creation')
            creation_id = creation_obj.search(cr, 1, [('dbname', '=',
                                                       cr.dbname)])
            creation_id = creation_id and creation_id[0] or []
            if not creation_id:
                nb_state = len(pool.get('instance.auto.creation')._columns['state'].selection) - 1
                percentage_per_step = 1/float(nb_state)
                return _('Empty database creation in progress...\n'), percentage_per_step, 'draft', ''
            res = creation_obj.read(cr, 1, creation_id, ['resume', 'progress',
                                                         'state', 'error'])

            # get the last sync_monitor informations:
            monitor_status = ''
            monitor_obj = pool.get('sync.monitor')
            if monitor_obj and pool._ready:
                monitor_id = monitor_obj.search(cr, 1, [], order='start desc', limit=1)
                monitor_id = monitor_id and monitor_id[0] or False
                if monitor_id:
                    result = monitor_obj.read(cr, 1, monitor_id, ['status', 'error'])
                    monitor_status = 'Synchronisation status: %s : %s' % (result['status'], result['error'])
        finally:
            cr.close()
        return res['resume'], res['progress'], res['state'], res['error'], monitor_status

    def exp_check_super_password_validity(self, password):
        try:
            security.check_super_password_validity(password)
        except Exception as e:
            return str(e)
        return True

    def exp_check_password_validity(self, login, password):
        try:
            security.check_password_validity(None, None, None, None, password, password, login)
        except Exception as e:
            return str(e)
        return True

    def exp_check_timezone(self):
        return check_tz()

    def exp_get_progress(self, id):
        if self.actions[id]['thread'].is_alive():
            #           return addons.init_progress[db_name]
            return (min(self.actions[id].get('progress', 0),0.95), [])
        else:
            clean = self.actions[id]['clean']
            if clean:
                users = self.actions[id]['users']
                self.actions.pop(id)
                return (1.0, users)
            else:
                e = self.actions[id]['exception']
                self.actions.pop(id)
                raise Exception(e)

    def exp_drop(self, db_name):
        _check_db_name(db_name)
        sql_db.close_db(db_name)
        logger = netsvc.Logger()

        db = sql_db.db_connect('template1')
        cr = db.cursor()
        cr.autocommit(True) # avoid transaction block
        drop_db = False
        try:
            try:
                cr.execute('DROP DATABASE "%s"' % db_name)  # ignore_sql_check
                drop_db = True
            except Exception as e:
                logger.notifyChannel("web-services", netsvc.LOG_ERROR,
                                     'DROP DB: %s failed:\n%s' % (db_name, e))
                raise Exception("Couldn't drop database %s: %s" % (db_name, e))
            else:
                logger.notifyChannel("web-services", netsvc.LOG_INFO,
                                     'DROP DB: %s' % (db_name))
        finally:
            cr.close()
            if drop_db and db_name in pooler.pool_dic:
                del pooler.pool_dic[db_name]
                if tools.config.get('save_db_name_in_config') == 'Y':
                    tools.config.delete_db_name(db_name)

        return True

    def _set_pg_psw_env_var(self):
        if tools.config['db_password']:
            os.environ['PGPASSWORD'] = tools.config['db_password']

    def _unset_pg_psw_env_var(self):
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']

    def exp_dump_file(self, db_name):
        _check_db_name(db_name)
        # get a tempfilename
        f = NamedTemporaryFile(delete=False)
        f_name = f.name
        f.close()
        res = tools.pg_dump(db_name, f_name)
        if res:
            raise Exception("Couldn't dump database")
        return f_name


    def exp_dump(self, db_name):
        _check_db_name(db_name)
        logger = netsvc.Logger()
        data, res = tools.pg_dump(db_name)
        if res:
            logger.notifyChannel("web-services", netsvc.LOG_ERROR,
                                 'DUMP DB: %s failed\n%s' % (db_name, data))
            raise Exception("Couldn't dump database")
        return base64.b64encode(data)

    def exp_restore_file(self, db_name, filename):
        _check_db_name(db_name)
        try:
            logger = netsvc.Logger()

            self._set_pg_psw_env_var()

            if self.exp_db_exist(db_name):
                logger.notifyChannel("web-services", netsvc.LOG_WARNING,
                                     'RESTORE DB: %s already exists' % (db_name,))
                raise Exception("Database already exists")

            self._create_empty_database(db_name)

            cmd = ['pg_restore', '--no-owner', '--no-acl', '-n', 'public', '--single-transaction']
            if tools.config['db_user']:
                cmd.append('--username=' + tools.config['db_user'])
            if tools.config['db_host']:
                cmd.append('--host=' + tools.config['db_host'])
            if tools.config['db_port']:
                cmd.append('--port=' + str(tools.config['db_port']))
            cmd.append('--dbname=' + db_name)
            cmd.append(filename)
            res = tools.exec_pg_command(*cmd)
            os.remove(filename)
            if res:
                raise Exception("Couldn't restore database")

            logger.notifyChannel("web-services", netsvc.LOG_INFO,
                                 'RESTORE DB: %s' % (db_name))
            self._unset_pg_psw_env_var()

            return True
        except Exception:
            logging.getLogger('web-services').error("Restore %s failed" % (db_name, ), exc_info=1)
            raise

    def exp_restore(self, db_name, data):
        _check_db_name(db_name)
        logging.getLogger('web-services').info("Restore DB from memory")
        buf=base64.b64decode(data)
        tmpfile = NamedTemporaryFile('w+b', delete=False)
        tmpfile.write(buf)
        tmpfile.close()

        return self.exp_restore_file(db_name, tmpfile.name)

    def exp_rename(self, old_name, new_name):
        _check_db_name(old_name)
        _check_db_name(new_name)
        sql_db.close_db(old_name)
        logger = netsvc.Logger()

        db = sql_db.db_connect('template1')
        cr = db.cursor()
        cr.autocommit(True) # avoid transaction block
        try:
            try:
                cr.execute('ALTER DATABASE "%s" RENAME TO "%s"' % (old_name, new_name))  # ignore_sql_check
            except Exception as e:
                logger.notifyChannel("web-services", netsvc.LOG_ERROR,
                                     'RENAME DB: %s -> %s failed:\n%s' % (old_name, new_name, e))
                raise Exception("Couldn't rename database %s to %s: %s" % (old_name, new_name, e))
            else:
                fs = os.path.join(tools.config['root_path'], 'filestore')
                if os.path.exists(os.path.join(fs, old_name)):
                    os.rename(os.path.join(fs, old_name), os.path.join(fs, new_name))

                logger.notifyChannel("web-services", netsvc.LOG_INFO,
                                     'RENAME DB: %s -> %s' % (old_name, new_name))
        finally:
            cr.close()
        return True

    def exp_db_exist(self, db_name):
        _check_db_name(db_name)
        ## Not True: in fact, check if connection to database is possible. The database may exists
        return bool(sql_db.db_connect(db_name))

    def exp_list(self, document=False):
        if not tools.config['list_db'] and not document:
            raise Exception('AccessDenied')

        db = sql_db.db_connect('template1')
        cr = db.cursor()
        try:
            try:
                db_user = tools.config["db_user"]
                if not db_user and os.name == 'posix':
                    import pwd
                    db_user = pwd.getpwuid(os.getuid())[0]
                if not db_user:
                    cr.execute("select decode(usename, 'escape') from pg_user where usesysid=(select datdba from pg_database where datname=%s)", (tools.config["db_name"],))
                    res = cr.fetchone()
                    db_user = res and str(res[0])
                if db_user:
                    cr.execute("select decode(datname, 'escape') from pg_database where datdba=(select usesysid from pg_user where usename=%s) and datname not in ('template0', 'template1', 'postgres') order by datname", (db_user,))
                else:
                    cr.execute("select decode(datname, 'escape') from pg_database where datname not in('template0', 'template1','postgres') order by datname")
                res = [name.tobytes().decode('utf8') for (name,) in cr.fetchall()]
            except Exception:
                res = []
        finally:
            cr.close()
        res.sort()
        return res

    def exp_connected_to_prod_sync_server(self, db_name):
        """Return True if db_name is connected to a production SYNC_SERVER,
        False otherwise"""

        _check_db_name(db_name)
        connection = sql_db.db_connect(db_name)
        # it the db connnected to a sync_server ?
        server_connecion_module = pooler.get_pool(db_name, upgrade_modules=False).get('sync.client.sync_server_connection')
        if not server_connecion_module:
            return False

        if not getattr(server_connecion_module, '_uid', False):
            return False

        prod = False
        cr = connection.cursor()
        try:
            prod = tools.misc.use_prod_sync(cr)
        finally:
            cr.close()
        return prod

    def exp_change_admin_password(self, new_password):
        tools.config['admin_passwd'] = new_password
        tools.config.save()
        return True

    def exp_list_lang(self):
        return tools.scan_languages()

    def exp_server_version(self, dbname=False):
        """ Return the version of the server from the sql table
        sync_client_version. If it's not found return the version found from
        the unified-version.txt (old base)
            Used by the client to verify the compatibility with its own version
        """
        if not dbname:
            return release.version
        _check_db_name(dbname)

        db = sql_db.db_connect(dbname)
        cr = db.cursor()

        try:
            # check sync_client_version table existance
            cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname='sync_client_version'")
            if not cr.fetchone():
                # the table sync_client_version doesn't exists, fallback on the
                # version from release.py file
                return release.version or 'UNKNOWN_VERSION'

            cr.execute("SELECT name, sum FROM sync_client_version WHERE state='installed' ORDER BY applied DESC")
            res = cr.fetchone()
        finally:
            cr.close(True)
        if res and res[0]:
            return res[0]
        elif res[1]:
            version_list = get_server_version()
            for version in version_list:
                if res[1] == version['md5sum'] and version['name']:
                    return version['name']
        return 'UNKNOWN_VERSION'

    def exp_migrate_databases(self,databases):

        from osv.orm import except_orm
        from osv.osv import except_osv

        l = netsvc.Logger()
        for db in databases:
            try:
                l.notifyChannel('migration', netsvc.LOG_INFO, 'migrate database %s' % (db,))
                tools.config['update']['base'] = True
                pooler.restart_pool(db, force_demo=False, update_module=True)
            except except_orm as inst:
                self.abortResponse(1, inst.name, 'warning', inst.value)
            except except_osv as inst:
                self.abortResponse(1, inst.name, inst.exc_type, inst.value)
            except Exception:
                import traceback
                tb_s = reduce(lambda x, y: x+y, traceback.format_exception( sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]))
                l.notifyChannel('web-services', netsvc.LOG_ERROR, tb_s)
                raise
        return True
db()

class _ObjectService(netsvc.ExportService):
    "A common base class for those who have fn(db, uid, password,...) "

    def common_dispatch(self, method, auth, params):
        (db, uid, passwd ) = params[0:3]
        params = params[3:]
        security.check(db,uid,passwd)
        cr = pooler.get_db(db).cursor()
        try:
            fn = getattr(self, 'exp_'+method)
            res = fn(cr, uid, *params)
            cr.commit()
        finally:
            cr.close()
        return res

class common(_ObjectService):
    def __init__(self,name="common"):
        _ObjectService.__init__(self,name)
        self.joinGroup("web-services")

    def dispatch(self, method, auth, params):
        logger = netsvc.Logger()
        if method in [ 'ir_set','ir_del', 'ir_get' ]:
            return self.common_dispatch(method,auth,params)
        if method == 'login':
            # At this old dispatcher, we do NOT update the auth proxy
            res = security.login(params[0], params[1], params[2])
            msg = res and 'successful login' or 'bad login or password'
            # TODO log the client ip address..
            if params[1].lower() != 'unidata':
                logger.notifyChannel("web-service", netsvc.LOG_INFO, "%s from '%s' using database '%s'" % (msg, params[1], params[0].lower()))
            return res or False
        elif method == 'number_update_modules':
            return security.number_update_modules(params[0])
        elif method == 'get_user_email':
            return security.get_user_email(params[0], params[1], params[2])
        elif method == 'change_password':
            try:
                security.change_password(params[0], params[1], params[2],
                                         params[3], params[4], params[5])
            except Exception as e:
                if hasattr(e, 'value'):
                    msg = tools.ustr(e.value)
                else:
                    msg = tools.ustr(e)
                return msg
            return True
        elif method == 'logout':
            if auth:
                auth.logout(params[1])
            logger.notifyChannel("web-service", netsvc.LOG_INFO,'Logout %s from database %s' % (params[1], db))
            return True
        elif method in ['about', 'timezone_get', 'get_server_environment',
                        'login_message','get_stats', 'check_connectivity',
                        'list_http_services']:
            pass
        elif method in ['get_available_updates', 'get_migration_scripts', 'set_loglevel', 'get_os_time', 'get_sqlcount']:
            passwd = params[0]
            params = params[1:]
            security.check_super(passwd)
        else:
            raise Exception("Method not found: %s" % method)

        fn = getattr(self, 'exp_'+method)
        return fn(*params)


    def new_dispatch(self,method,auth,params):
        pass

    def exp_ir_set(self, cr, uid, keys, args, name, value, replace=True, isobject=False):
        res = ir.ir_set(cr,uid, keys, args, name, value, replace, isobject)
        return res

    def exp_ir_del(self, cr, uid, id):
        res = ir.ir_del(cr,uid, id)
        return res

    def exp_ir_get(self, cr, uid, keys, args=None, meta=None, context=None):
        if not args:
            args=[]
        if not context:
            context={}
        res = ir.ir_get(cr,uid, keys, args, meta, context)
        return res

    def exp_about(self, extended=False):
        """Return information about the OpenERP Server.

        @param extended: if True then return version info
        @return string if extended is False else tuple
        """

        info = _('''

OpenERP is an ERP+CRM program for small and medium businesses.

The whole source code is distributed under the terms of the
GNU Public Licence.

(c) 2003-TODAY, Fabien Pinckaers - Tiny sprl''')

        if extended:
            return info, release.version
        return info

    def exp_timezone_get(self, db, login, password):
        return tools.misc.get_server_timezone()

    def exp_get_available_updates(self, contract_id, contract_password):
        import tools.maintenance as tm
        try:
            rc = tm.remote_contract(contract_id, contract_password)
            if not rc.id:
                raise tm.RemoteContractException('This contract does not exist or is not active')

            return rc.get_available_updates(rc.id, addons.get_modules_with_version())

        except tm.RemoteContractException as e:
            self.abortResponse(1, 'Migration Error', 'warning', str(e))


    def exp_get_migration_scripts(self, contract_id, contract_password):
        l = netsvc.Logger()
        import tools.maintenance as tm
        try:
            rc = tm.remote_contract(contract_id, contract_password)
            if not rc.id:
                raise tm.RemoteContractException('This contract does not exist or is not active')
            if rc.status != 'full':
                raise tm.RemoteContractException('Can not get updates for a partial contract')

            l.notifyChannel('migration', netsvc.LOG_INFO, 'starting migration with contract %s' % (rc.name,))

            zips = rc.retrieve_updates(rc.id, addons.get_modules_with_version())

            from shutil import rmtree, copytree, copy

            backup_directory = os.path.join(tools.config['root_path'], 'backup', time.strftime('%Y-%m-%d-%H-%M'))
            if zips and not os.path.isdir(backup_directory):
                l.notifyChannel('migration', netsvc.LOG_INFO, 'create a new backup directory to \
                                store the old modules: %s' % (backup_directory,))
                os.makedirs(backup_directory)

            for module in zips:
                l.notifyChannel('migration', netsvc.LOG_INFO, 'upgrade module %s' % (module,))
                mp = addons.get_module_path(module)
                if mp:
                    if os.path.isdir(mp):
                        copytree(mp, os.path.join(backup_directory, module))
                        if os.path.islink(mp):
                            os.unlink(mp)
                        else:
                            rmtree(mp)
                    else:
                        copy(mp + 'zip', backup_directory)
                        os.unlink(mp + '.zip')

                try:
                    try:
                        base64_decoded = base64.b64decode(zips[module])
                    except Exception:
                        l.notifyChannel('migration', netsvc.LOG_ERROR, 'unable to read the module %s' % (module,))
                        raise

                    zip_contents = StringIO(base64_decoded)
                    zip_contents.seek(0)
                    try:
                        try:
                            tools.extract_zip_file(zip_contents, tools.config['addons_path'] )
                        except Exception:
                            l.notifyChannel('migration', netsvc.LOG_ERROR, 'unable to extract the module %s' % (module, ))
                            rmtree(module)
                            raise
                    finally:
                        zip_contents.close()
                except Exception:
                    l.notifyChannel('migration', netsvc.LOG_ERROR, 'restore the previous version of the module %s' % (module, ))
                    nmp = os.path.join(backup_directory, module)
                    if os.path.isdir(nmp):
                        copytree(nmp, tools.config['addons_path'])
                    else:
                        copy(nmp+'.zip', tools.config['addons_path'])
                    raise

            return True
        except tm.RemoteContractException as e:
            self.abortResponse(1, 'Migration Error', 'warning', str(e))
        except Exception:
            import traceback
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception( sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]))
            l.notifyChannel('migration', netsvc.LOG_ERROR, tb_s)
            raise

    def exp_get_server_environment(self):
        os_lang = '.'.join( [x for x in locale.getdefaultlocale() if x] )
        if not os_lang:
            os_lang = 'NOT SET'
        environment = '\nEnvironment Information : \n' \
            'System : %s\n' \
            'OS Name : %s\n' \
            %(platform.platform(), platform.os.name)
        if os.name == 'posix':
            if platform.system() == 'Linux':
                lsbinfo = os.popen('lsb_release -a').read()
                environment += '%s'%(lsbinfo)
            else:
                environment += 'Your System is not lsb compliant\n'
        environment += 'Operating System Release : %s\n' \
            'Operating System Version : %s\n' \
            'Operating System Architecture : %s\n' \
            'Operating System Locale : %s\n'\
            'Python Version : %s\n'\
            'OpenERP-Server Version : %s'\
            %(platform.release(), platform.version(), platform.architecture()[0],
              os_lang, platform.python_version(),release.version)
        return environment

    def exp_login_message(self):
        return tools.config.get('login_message', False)

    def exp_set_loglevel(self, loglevel, logger=None):
        l = netsvc.Logger()
        l.set_loglevel(int(loglevel), logger)
        return True

    def exp_get_stats(self):
        import threading
        res = "OpenERP server: %d threads\n" % threading.active_count()
        res += netsvc.Server.allStats()
        return res

    def exp_list_http_services(self):
        from service import http_server
        return http_server.list_http_services()

    def exp_check_connectivity(self):
        return bool(sql_db.db_connect('template1'))

    def exp_get_os_time(self):
        return os.times()

    def exp_get_sqlcount(self):
        logger = logging.getLogger('db.cursor')
        if not logger.isEnabledFor(logging.DEBUG_SQL):
            logger.warning("Counters of SQL will not be reliable unless DEBUG_SQL is set at the server's config.")
        return sql_db.sql_counter

common()

class objects_proxy(netsvc.ExportService):
    def __init__(self, name="object"):
        netsvc.ExportService.__init__(self,name)
        self.joinGroup('web-services')

    def dispatch(self, method, auth, params):
        (db, uid, passwd ) = params[0:3]
        params = params[3:]
        if method == 'obj_list':
            raise NameError("obj_list has been discontinued via RPC as of 6.0, please query ir.model directly!")
        if method not in ['execute','exec_workflow']:
            raise NameError("Method not available %s" % method)
        security.check(db,uid,passwd)
        ls = netsvc.LocalService('object_proxy')
        fn = getattr(ls, method)
        res = fn(db, uid, *params)
        return res


    def new_dispatch(self,method,auth,params):
        pass

objects_proxy()


#
# Wizard ID: 1
#    - None = end of wizard
#
# Wizard Type: 'form'
#    - form
#    - print
#
# Wizard datas: {}
# TODO: change local request to OSE request/reply pattern
#
class wizard(netsvc.ExportService):
    def __init__(self, name='wizard'):
        netsvc.ExportService.__init__(self,name)
        self.joinGroup('web-services')
        self.id = 0
        self.wiz_datas = {}
        self.wiz_name = {}
        self.wiz_uid = {}

    def dispatch(self, method, auth, params):
        (db, uid, passwd ) = params[0:3]
        params = params[3:]
        if method not in ['execute','create']:
            raise KeyError("Method not supported %s" % method)
        security.check(db,uid,passwd)
        fn = getattr(self, 'exp_'+method)
        res = fn(db, uid, *params)
        return res

    def new_dispatch(self,method,auth,params):
        pass

    def _execute(self, db, uid, wiz_id, datas, action, context):
        self.wiz_datas[wiz_id].update(datas)
        wiz = netsvc.LocalService('wizard.'+self.wiz_name[wiz_id])
        return wiz.execute(db, uid, self.wiz_datas[wiz_id], action, context)

    def exp_create(self, db, uid, wiz_name, datas=None):
        if not datas:
            datas={}
#FIXME: this is not thread-safe
        self.id += 1
        self.wiz_datas[self.id] = {}
        self.wiz_name[self.id] = wiz_name
        self.wiz_uid[self.id] = uid
        return self.id

    def exp_execute(self, db, uid, wiz_id, datas, action='init', context=None):
        if not context:
            context={}

        if wiz_id in self.wiz_uid:
            if self.wiz_uid[wiz_id] == uid:
                return self._execute(db, uid, wiz_id, datas, action, context)
            else:
                raise Exception('AccessDenied')
        else:
            raise Exception('WizardNotFound')
wizard()

#
# TODO: set a maximum report number per user to avoid DOS attacks
#
# Report state:
#     False -> True
#

class ExceptionWithTraceback(Exception):
    def __init__(self, msg, tb):
        self.message = msg
        self.traceback = tb
        self.args = (msg, tb)

class report_spool(netsvc.ExportService):
    def __init__(self, name='report'):
        netsvc.ExportService.__init__(self, name)
        self.joinGroup('web-services')
        self._reports = {}
        self._exports = {}
        self.id = 0
        self.id_protect = threading.Semaphore()

    def dispatch(self, method, auth, params):
        (db, uid, passwd ) = params[0:3]
        params = params[3:]
        if method not in ['report','report_get', 'report_get_state', 'export']:
            raise KeyError("Method not supported %s" % method)
        security.check(db,uid,passwd)
        fn = getattr(self, 'exp_' + method)
        res = fn(db, uid, *params)
        return res


    def new_dispatch(self,method,auth,params):
        pass

    def get_grp_data(self, result, flds):
        data = []
        for r in result:
            tmp_data = []
            for f in flds:
                value = r.get(f,'')
                if isinstance(value, tuple):
                    value = value and value[1] or ''
                tmp_data.append(value)
            data.append(tmp_data)
        return data

    def exp_export(self, db_name, uid, fields, domain, model, fields_name,
                   group_by=None, export_format='csv', ids=None, context=None):
        res = {'result': None}
        db, pool = pooler.get_db_and_pool(db_name)
        cr = db.cursor()
        bg_obj = pool.get('memory.background.report')
        background_id = bg_obj.create(cr, uid, {})
        create_thread = threading.Thread(target=self.export,
                                         args=(cr, pool, uid, fields, domain, model, fields_name,
                                               background_id, group_by, export_format, ids, res, context))
        create_thread.start()

        # after 4 seconds, the progress bar is displayed
        create_thread.join(4)
        if res['result']:
            return res
        return background_id

    def export(self, cr, pool, uid, fields, domain, model, fields_name,
               bg_id, group_by=None, export_format='csv', ids=None, res=None,
               context=None):

        if not res:
            res={}
        if not context:
            context={}

        self.id_protect.acquire()
        self.id += 1
        report_id = self.id
        self.id_protect.release()
        model_obj = pool.get(model)
        view_name = context.get('_terp_view_name', '') or context.get('_terp_view_name_for_export', '')
        title = '%s_%s' % (view_name, time.strftime('%Y%m%d'))
        self._reports[report_id] = {
            'uid': uid,
            'result': False,
            'state': False,
            'exception': None,
            'format': export_format,
            'filename': title,
            'psql_pid': cr._cnx.get_backend_pid(),
        }

        bg_obj = pool.get('memory.background.report')
        bg_obj.write(cr, uid, [bg_id],
                     {
                     'report_name': title,
                     'report_id': report_id,
                     'percent': 0.00,
                     'finished': False
                     }, context=context)

        if not ids:
            ids = model_obj.search(cr, uid, domain, context=context)

        result_file = NamedTemporaryFile('w+b', delete=False)
        result_file_path = result_file.name
        result_file.close()
        if group_by:
            data = model_obj.read_group(cr, uid, domain, fields, group_by, 0, 0, context=context)

            result_tmp = []  # List of processed data lines (dictionaries)
            # Closure to recursively prepare and insert lines in 'result_tmp'
            # (as much as the number of 'group_by' levels)
            def process_data(line):
                domain_line = line.get('__domain', [])
                grp_by_line = line.get('__context', {}).get('group_by', [])
                # If there is a 'group_by', we fetch data one level deeper
                if grp_by_line:
                    data = model_obj.read_group(cr, uid, domain_line, fields, grp_by_line, 0, 0, context=context)
                    for line2 in data:
                        line_copy = line.copy()
                        line_copy.update(line2)
                        process_data(line_copy)
                # If 'group_by' is empty, this means we were at the last level
                # so we insert the line in the final result
                else:
                    result_tmp.append(line)
            # Prepare recursively the data to export (inserted in 'result_tmp')
            counter = 0
            for data_line in data:
                counter += 1
                process_data(data_line)
                progression = float(counter) / len(data)
                bg_obj.update_percent(cr, uid, bg_id, progression, context=context)
            result = self.get_grp_data(result_tmp, fields)

            result, fields_name = model_obj.filter_export_data_result(cr, uid, result, fields_name)
        else:

            result = {'datas': []}
            counter = 0
            chunk_size = 100
            for i in range(0, len(ids), chunk_size):
                ids_chunk = ids[i:i + chunk_size]
                counter += len(ids_chunk)
                result['datas'].extend(model_obj.export_data(cr, uid, ids_chunk, fields,
                                                             context=context)['datas'])
                progression = float(counter) / len(ids)
                bg_obj.update_percent(cr, uid, bg_id, progression, context=context)

            if result.get('warning'):
                common.warning(str(result.get('warning', False)), _('Export Error'))
                res['result'] = False
                return False
            result = result.get('datas',[])

        if export_format == "xls":
            with codecs.open(result_file_path, 'wb', 'utf8') as result_file:
                f, filename = file_open('addons/base/report/templates/expxml.mako', pathinfo=True)
                f[0].close()
                body_mako_tpl = Template(filename=filename, input_encoding='utf-8', default_filters=['unicode'])
                try:
                    fields_name = [tools.ustr(x) for x in fields_name]
                    mako_ctx = Context(result_file, fields=fields_name,
                                       result=result, title=title, re=re,
                                       isDate=report_sxw.isDate)
                    logging.getLogger('web-services').info('Start rendering report %s...' % filename)
                    body_mako_tpl.render_context(mako_ctx)
                    logging.getLogger('web-services').info('report generated.')
                except Exception:
                    msg = exceptions.text_error_template().render()
                    netsvc.Logger().notifyChannel('Webkit render', netsvc.LOG_ERROR, msg)
                    raise osv.except_osv(_('Webkit render'), msg)
        elif export_format == 'csv':
            export_csv(fields, result, result_file_path)
        else:
            with open(result_file_path, 'wb') as result_file:
                result_file.write(result)
        res['result'] = result_file_path
        self._reports[report_id]['path'] = result_file_path
        self._reports[report_id]['state'] = True
        bg_obj.write(cr, uid, [bg_id],
                     {
                     'file_name': result_file_path,
                     'percent': 1.00,
                     }, context=context)
        cr.commit()
        cr.close()
        return result_file_path

    def exp_report(self, db_name, uid, object, ids, datas=None, context=None):
        if not datas:
            datas={}
        if not context:
            context={}

        self.id_protect.acquire()
        self.id += 1
        id = self.id
        self.id_protect.release()

        self._reports[id] = {'uid': uid, 'result': False, 'state': False, 'exception': None}

        def go(id, uid, ids, datas, context):
            cr = pooler.get_db(db_name).cursor()
            self._reports[id]['psql_pid'] = cr._cnx.get_backend_pid()
            import traceback
            import sys
            try:
                obj = netsvc.LocalService('report.'+object)
                bg_obj = pooler.get_pool(cr.dbname).get('memory.background.report')
                if context.get('background_id'):
                    context['pathit'] = True
                (result, format) = obj.create(cr, uid, ids, datas, context)
                if not result:
                    tb = sys.exc_info()
                    self._reports[id]['exception'] = ExceptionWithTraceback('RML is not available at specified location or not enough data to print!', tb)
                if context.get('background_id'):
                    bg_obj.update_percent(cr, uid, context['background_id'],
                                          percent=1.00, context=context)
                if isinstance(result, tools.misc.Path):
                    self._reports[id]['path'] = result.path
                    self._reports[id]['result'] = ''
                    self._reports[id]['delete'] = result.delete
                else:
                    self._reports[id]['result'] = result
                self._reports[id]['format'] = format
                self._reports[id]['state'] = True
            except Exception as exception:
                if not self._reports[id].get('killed'):
                    tb = sys.exc_info()
                    tb_s = "".join(traceback.format_exception(*tb))
                    logger = netsvc.Logger()
                    logger.notifyChannel('web-services', netsvc.LOG_ERROR,
                                         'Exception: %s\n%s' % (tools.ustr(exception), tb_s))
                    if hasattr(exception, 'name') and hasattr(exception, 'value'):
                        self._reports[id]['exception'] = ExceptionWithTraceback(tools.ustr(exception.name), tools.ustr(exception.value))
                    else:
                        self._reports[id]['exception'] = ExceptionWithTraceback(tools.exception_to_unicode(exception), tb)
                self._reports[id]['state'] = True
            finally:
                cr.commit()
                cr.close()
            return True

        _thread.start_new_thread(go, (id, uid, ids, datas, context))
        return id

    def _check_report(self, report_id):
        result = self._reports[report_id]
        exc = result['exception']
        if exc:
            self.abortResponse(exc, exc.message, 'warning', exc.traceback)
        res = {'state': result['state']}
        if 'filename' in result and 'format' in result:
            res['filename'] = '%s.%s' % (result['filename'], result['format'])
        if res['state']:
            if tools.config['reportgz']:
                import zlib
                res2 = zlib.compress(result['result'])
                res['code'] = 'zlib'
            else:
                res2 = result['result']
            if res2:
                if isinstance(res2, str):
                    res2 = bytes(res2, 'utf8')
                res['result'] = base64.b64encode(res2).decode('utf8')
            res['format'] = result['format']
            if 'path' in result:
                res['path'] = result['path']
                res['delete'] = result.get('delete', False)
            del self._reports[report_id]
        return res

    def exp_report_get_state(self, db, uid, report_id):
        if report_id in self._reports:
            if self._reports[report_id]['uid'] == uid:
                result = self._reports[report_id]
                return result['state']
            else:
                raise Exception('AccessDenied')
        else:
            raise Exception('ReportNotFound')

    def exp_report_get(self, db, uid, report_id):
        if report_id in self._reports:
            if self._reports[report_id]['uid'] == uid:
                return self._check_report(report_id)
            else:
                raise Exception('AccessDenied')
        else:
            raise Exception('ReportNotFound')

report_spool()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
