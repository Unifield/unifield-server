# -*- coding: utf-8 -*-
"""
Unifield module to upgrade the instance to a next version of Unifield
Beware that we expect to be in the bin/ directory to proceed!!
"""
from __future__ import with_statement
import re
import os
import ctypes
import platform
import tempfile
import sys
import shutil
from hashlib import md5
from datetime import datetime
import time
from base64 import b64decode
from StringIO import StringIO
import logging
import subprocess
import base64
from zipfile import ZipFile
import bsdifftree

__all__ = ('isset_lock', 'server_version', 'base_version', 'do_prepare', 'base_module_upgrade', 'restart_server')

restart_required = False
if sys.platform == 'win32' and os.path.isdir(r'..\ServerLog'):
    log_file = r'..\ServerLog\updater.log'
else:
    log_file = 'updater.log'
lock_file = 'update.lock'
update_dir = '.update'
server_version_file = 'unifield-version.txt'
new_version_file = os.path.join(update_dir, 'update-list.txt')
restart_delay = 5

md5hex_size = (md5().digest_size * 8 / 4)
base_version = '8' * md5hex_size
# match 3 groups : md5sum <space> date (yyyy-mm-dd hh:mm:ss) <space> version
#example : 694d9c65bce826551df26cefcc6565e1 2015-11-27 16:15:00 UF2.0rc3
re_version = re.compile(r'^\s*([a-fA-F0-9]{'+str(md5hex_size)+r'}\b)\s*(\d+-\d+-\d+\s*\d+:\d+:\d+)\s*(.*)')
logger = logging.getLogger('updater')

def restart_server():
    """Restart OpenERP server"""
    global restart_required
    logger.info("Restaring OpenERP Server in %d seconds..." % restart_delay)
    restart_required = True

def isset_lock(file=None):
    """Check if server lock file is set"""
    if file is None: file = lock_file
    return os.path.isfile(lock_file)

def set_lock(file=None):
    """Set the lock file to make OpenERP run into do_update method against normal execution"""
    if file is None: file = lock_file
    with open(file, "w") as f:
        f.write(unicode({'path':os.getcwd()}))

def unset_lock(file=None):
    """Remove the lock"""
    global exec_path
    if file is None: file = lock_file
    with open(file, "r") as f:
        data = eval(f.read().strip())
        exec_path = data['path']
    os.unlink(file)

def parse_version_file(filepath):
    """Short method to parse a "version file"
    Basically, a file where each line starts with the sum of a patch"""
    assert os.path.isfile(filepath), "The file `%s' must be a file!" % filepath
    versions = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.rstrip()
            if not line: continue
            try:
                result = re_version.findall(line)
                if not result: continue
                md5sum, date, version_name = result[0]
                versions.append({'md5sum': md5sum,
                                 'date': date,
                                 'name': version_name,
                                 })
            except AttributeError:
                raise Exception("Unable to parse version from file `%s': %s" % (filepath, line))
    return versions

def get_server_version():
    """Autocratically get the current versions of the server
    Get a special key 88888888888888888888888888888888 for default value if no server version can be found"""
    if not os.path.exists(server_version_file):
        return [base_version]
    return parse_version_file(server_version_file)

def add_versions(versions, filepath=server_version_file):
    """Set server version with new versions"""
    if not versions:
        return
    with open(filepath, 'a') as f:
        for ver in versions:
            f.write((" ".join([unicode(x) for x in ver]) if hasattr(ver, '__iter__') else ver)+os.linesep)

def find(path):
    """Unix-like find"""
    files = os.listdir(path)
    for name in iter(files):
        abspath = path+os.path.sep+name
        if os.path.isdir( abspath ) and not os.path.islink( abspath ):
            files.extend( map(lambda x:name+os.path.sep+x, os.listdir(abspath)) )
    return files

def rmtree(files, path=None, verbose=False):
    """Python free rmtree"""
    #  OpenERPServerService.exe can't be deleted if Windows Service MAnager uses it
    backup_trash = 'backup-trash'
    if path is None and isinstance(files, basestring):
        path, files = files, find(files)
    for f in reversed(files):
        target = os.path.join(path, f) if path is not None else f
        if os.path.isfile(target) or os.path.islink(target):
            warn("unlink", target)
            try:
                os.unlink(target)
            except:
                warn('Except on target %s' % (target,))
                if target.endswith('.exe'):
                    if not os.path.isdir(backup_trash):
                        os.makedirs(backup_trash)
                    index = 0
                    newname = os.path.join(backup_trash, '%s-%s' % (os.path.basename(target), index))
                    while os.path.isfile(newname):
                        index += 1
                        newname = os.path.join(backup_trash, '%s-%s' % (os.path.basename(target), index))
                    os.rename(target, newname)
                else:
                    raise
        elif os.path.isdir(target):
            warn("rmdir", target)
            os.rmdir( target )

def now():
    return datetime.today().strftime("%Y-%m-%d %H:%M:%S")

log = sys.stderr

def warn(*args):
    """Define way to forward logs"""
    global log
    try:
        log.write(("[%s] UPDATER: " % now())+" ".join(map(lambda x:unicode(x), args))+os.linesep)
    except:
        try:
            log.write(("[%s] UPDATER: " % now())+" ".join(map(lambda x:unicode(x.decode('utf-8', errors='ignore')), args))+os.linesep)
        except:
            log.write("[%s] UPDATER: unknown error" % now())
    log.flush()


def Try(command):
    """Try...Resume..."""
    try:
        command()
    except BaseException, e:
        warn(unicode(e))
        return False
    else:
        return True



##############################################################################
##                                                                          ##
##  Main methods of updater modules                                         ##
##                                                                          ##
##############################################################################


def base_module_upgrade(cr, pool, upgrade_now=False):
    """Just like -u base / -u all.
    Arguments are:
     * cr: cursor to the database
     * pool: pool of the same db
     * (optional) upgrade_now: False by default, on True, it will launch the process right now"""
    modules = pool.get('ir.module.module')
    base_ids = modules.search(cr, 1, [('name', '=', 'base')])
    #base_ids = modules.search(cr, 1, [('name', '=', 'sync_client')]) #for tests
    modules.button_upgrade(cr, 1, base_ids)
    if upgrade_now:
        logger.info("--------------- STARTING BASE UPGRADE PROCESS -----------------")
        pool.get('base.module.upgrade').upgrade_module(cr, 1, [])
        script = pool.get('patch.scripts')
        not_run = False
        if script:
            not_run = script.search(cr, 1, [('run', '=', False)])
            if not_run:
                logger.warn("%d patch scripts are not run" % len(not_run))
        bad_modules = modules.search(cr, 1, [('state', 'in', ['to upgrade', 'to install', 'to remove'])])
        if bad_modules:
            logger.warn("%d modules not upgraded" % len(bad_modules))

        if not not_run and not bad_modules:
            logger.info("--------------- PATCH APPLIED ---------------")
        else:
            logger.info("--------------- ISSUES WITH PATCH APPLICATION ---------------")

def process_deletes(update_dir, webpath):
    delfile = os.path.join(update_dir, 'delete.txt')
    if not os.path.exists(delfile):
        return

    deleted = []
    with open(delfile) as f:
        for line in f:
            line = line.strip()
            if line.startswith("web/"):
                src = os.path.join(webpath, line[4:])
                dest = os.path.join(webpath, 'backup', line[4:])
            else:
                src = line
                dest = os.path.join('backup', line)

            destdir = os.path.dirname(dest)
            if not os.path.exists(destdir):
                warn("Making new destdir: %s" % destdir)
                os.makedirs(destdir)
            if os.path.exists(src):
                warn("Delete: %s" % src)
                os.rename(src, dest)
                deleted.append(line)
            else:
                warn("File to delete %s not found." % src)
    return deleted

def is_webfile(f):
    return re.match("^web[\\\/](.*)", f)

def do_update():
    """Real update of the server (before normal OpenERP execution).
    This function is triggered when OpenERP starts. When it finishes, it restart OpenERP automatically.
    On failure, the lock file is deleted and OpenERP files are rollbacked to their previous state."""
    if isset_lock() and Try(unset_lock):
        global log
        ## Move logs log file
        try:
            log = open(log_file, 'a')
        except BaseException, e:
            warn("Cannot write into `%s': %s" % (log, unicode(e)))
        else:
            warn(lock_file, 'removed')
        ## Now, update
        revisions = []
        files = []
        deleted_files = []
        try:
            ## Revisions that going to be installed
            revisions = parse_version_file(new_version_file)
            os.unlink(new_version_file)
            ## Explore .update directory

            ## Prepare backup directory
            if not os.path.exists('backup'):
                os.mkdir('backup')
            else:
                rmtree('backup')

            if os.name == "nt":
                import _winreg

                try:
                    registry_key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, "SYSTEM\ControlSet001\services\eventlog\Application\openerp-web-6.0", 0,
                                                   _winreg.KEY_READ)
                    value, regtype = _winreg.QueryValueEx(registry_key, "EventMessageFile")
                    _winreg.CloseKey(registry_key)
                    regval = value
                    warn("webmode registry key : %s" % regval)
                except WindowsError:
                    warn("webmode registry key not found")
                    regval = "c:\Program Files (x86)\msf\Unifield\Web\service\libs\servicemanager.pyd"

                res = re.match("^(.*)\\\\service\\\\libs\\\\servicemanager.pyd", regval)
                if res:
                    webpath = res.group(1)
                else:
                    webpath = "c:\\Program Files (x86)\\msf\\Unifield\\Web"

            else:
                #We're on the runbot
                webpath = '../../unifield-web/'
            webbackup = os.path.join(webpath, 'backup')
            if not os.path.exists(webbackup):
                os.mkdir(webbackup)
            else:
                rmtree(webbackup)

            webupdated = False
            ## Update Files
            warn("Updating...")
            files = find(update_dir)
            for f in files:
                # The delete list is handled last.
                if f == 'delete.txt':
                    continue

                webfile = is_webfile(f)
                warn("Filename : `%s'" % (f))
                if webfile:
                    target = os.path.join(update_dir, f)
                    bak = os.path.join(webbackup, webfile.group(1))
                    webf = os.path.join(webpath, webfile.group(1))
                    warn("webmode (webpath, target, bak, webf): %s, %s, %s, %s" % (webpath, target, bak, webf))
                    if os.path.isdir(target):
                        if os.path.isfile(webf) or os.path.islink(webf):
                            os.unlink(webf)
                        if not os.path.exists(webf):
                            os.mkdir(webf)
                        os.mkdir(bak)
                    else:
                        if os.path.exists(webf):
                            warn("`%s' -> `%s'" % (webf, bak))
                            os.rename(webf, bak)
                        warn("`%s' -> `%s'" % (target, webf))
                        os.rename(target, webf)
                    webupdated = True
                else:
                    target = os.path.join(update_dir, f)
                    bak = os.path.join('backup', f)

                    if os.path.isdir(target):
                        if os.path.isfile(f) or os.path.islink(f):
                            os.unlink(f)
                        if not os.path.exists(f):
                            os.mkdir(f)
                        os.mkdir(bak)
                    else:
                        if os.path.exists(f):
                            warn("`%s' -> `%s'" % (f, bak))
                            os.rename(f, bak)
                        warn("`%s' -> `%s'" % (target, f))
                        os.rename(target, f)

            # Read and apply the deleted.txt file.
            deleted_files = process_deletes(update_dir, webpath)

            # Clean out the PYC files so that they can be recompiled
            # by the (potentially) updated pythonXX.dll.
            for d in [ '.', webpath ]:
                for root, dirs, o_files in os.walk(d):
                    for file in o_files:
                        if file.endswith('.pyc'):
                            file = os.path.join(root, file)
                            warn('Purge pyc: %s' % file)
                            try:
                                os.unlink(file)
                            except:
                                # in some cases pyc is locked by another process (virus scan?)
                                pass

            shutil.copy(server_version_file, 'backup')
            files.append(server_version_file)
            add_versions([(x['md5sum'], x['date'],
                           x['name']) for x in revisions])
            warn("Update successful.")
            warn("Revisions added: ", ", ".join([x['md5sum'] for x in revisions]))
            ## No database update here. I preferred to set modules to update just after the preparation
            ## The reason is, when pool is populated, it will starts by upgrading modules first
            #Restart web server
            if webupdated and os.name == "nt":
                try:
                    subprocess.call('net stop "OpenERP Web 6.0"')
                    subprocess.call('net start "OpenERP Web 6.0"')
                except OSError, e:
                    warn("Exception in Web server restart :")
                    warn(unicode(e))

        except BaseException, e:
            warn("Update failure!")
            try:
                warn(unicode(e))
            except:
                warn("Unknown error")
            ## Restore backup and purge .update
            if files or deleted_files:
                warn("Restoring... ")
                for f in reversed(files + deleted_files):
                    webfile = is_webfile(f)
                    if webfile:
                        f = os.path.join(webpath, webfile.group(1))
                        target = os.path.join(webbackup, webfile.group(1))
                    else:
                        target = os.path.join('backup', f)
                    if os.path.isfile(target) or os.path.islink(target):
                        warn("`%s' -> `%s'" % (target, f))
                        if os.path.isfile(f):
                            os.remove(f)
                        dest_dir = os.path.dirname(f)
                        if dest_dir and not os.path.isdir(dest_dir):
                            os.makedirs(dest_dir)
                        os.rename(target, f)
                warn("Purging...")
                Try(lambda:rmtree(update_dir))
        if os.name == 'nt':
            warn("Exiting OpenERP Server with code 1 to tell service to restart")
            sys.exit(1) # require service to restart
        else:
            warn(("Restart OpenERP in %s:" % exec_path), \
                 [sys.executable]+sys.argv)
            if log is not sys.stderr:
                log.close()
            os.chdir(exec_path)
            os.execv(sys.executable, [sys.executable] + sys.argv)


def update_path():
    """If server starts normally, this step will fix the paths with the configured path in config rc"""
    from tools import config
    for v in ('log_file', 'lock_file', 'update_dir', 'server_version_file', 'new_version_file'):
        globals()[v] = os.path.join(config['root_path'], globals()[v])
    global server_version
    server_version = get_server_version()


def do_prepare(cr, revision_ids):
    """Prepare patches for an upgrade of the server and set the lock file"""
    if not revision_ids:
        return ('failure', 'Nothing to do.', {})
    import pooler
    pool = pooler.get_pool(cr.dbname)
    version = pool.get('sync_client.version')

    # Make an update temporary path
    path = update_dir
    if not os.path.exists(path):
        os.mkdir(path)
    else:
        for f in reversed(find(path)):
            target = os.path.join(path, f)
            if os.path.isfile(target) or os.path.islink(target):
                logger.debug("rm `%s'" % target)
                os.unlink( target )
            elif os.path.isdir(target):
                logger.debug("rmdir `%s'" % target)
                os.rmdir( target )
    if not (os.path.isdir(path) and os.access(path, os.W_OK)):
        message = "The path `%s' is not a dir or is not writable!"
        logger.error(message % path)
        return ('failure', message, (path,))
    # Proceed all patches
    new_revisions = []
    corrupt = []
    missing = []
    need_restart = []
    for rev in version.browse(cr, 1, revision_ids):
        # Check presence of the patch
        if not rev.patch:
            missing.append(rev)
            continue
        # Check if the file match the expected sum
        patch = b64decode(rev.patch)
        local_sum = md5(patch).hexdigest()
        if local_sum != rev.sum:
            corrupt.append(rev)
        elif not (corrupt or missing):
            # Extract the Zip
            delete_file = os.path.join(path, 'delete.txt')
            tmp_del = False
            if os.path.exists(delete_file):
                tmp_del = os.path.join(path, 'delete-%s' % time.time())
                os.rename(delete_file, tmp_del)
            f = StringIO(patch)
            try:
                zip = ZipFile(f, 'r')
                zip.extractall(path)
            finally:
                f.close()
            if tmp_del:
                if os.path.exists(delete_file):
                    with open(tmp_del, 'a') as prev:
                        prev.write('\n')
                        with open(delete_file) as newdel:
                            prev.write(newdel.read())
                    os.remove(delete_file)
                os.rename(tmp_del, delete_file)

            # Store to list of updates
            new_revisions.append((rev.sum, ("%s %s" % (rev.date, rev.name))))
            if rev.state == 'not-installed':
                need_restart.append(rev.id)
    # Remove corrupted patches
    if corrupt:
        corrupt_ids = [x.id for x in corrupt]
        version.write(cr, 1, corrupt_ids, {'patch':False})
        if len(corrupt) == 1: message = "One file you downloaded seems to be corrupt:\n\n%s"
        else: message = "Some files you downloaded seem to be corrupt:\n\n%s"
        values = ""
        for rev in corrupt:
            values += " - %s (sum expected: %s)\n" % ((rev.name or 'unknown'), rev.sum)
        logger.error(message % values)
        return ('corrupt', message, values)
    # Complaints about missing patches
    if missing:
        if len(missing) == 1:
            message = "A file is missing: %(name)s (check sum: %(sum)s)"
            values = {
                'name' : missing[0].name or 'unknown',
                'sum' : missing[0].sum
            }
        else:
            message = "Some files are missing:\n\n%s"
            values = ""
            for rev in missing:
                values += " - %s (check sum: %s)\n" % ((rev.name or 'unknown'), rev.sum)
        logger.error(message % values)
        return ('missing', message, values)

    new_updater_version = os.path.join(path, 'Server', 'updater.py')
    logger.info('Updater.py status: %s %s'%(new_updater_version, os.path.isfile(new_updater_version)))
    if os.path.isfile(new_updater_version):
        logger.info('Copy %s'%new_updater_version)
        shutil.copy(new_updater_version, '.')

    # Fix the flag of the pending patches
    version.write(cr, 1, need_restart, {'state':'need-restart'})
    # Make a lock file to make OpenERP able to detect an update
    set_lock()
    add_versions(new_revisions, new_version_file)
    logger.info("Server update prepared. Need to restart to complete the upgrade.")
    return ('success', 'Restart required', {})

def test_do_upgrade(cr):
    cr.execute("select count(1) from pg_class where relkind='r' and relname='sync_client_version'")
    if not cr.fetchone()[0]:
        return False

    cr.execute("select sum from sync_client_version where state='installed'")
    db_versions = []
    for ver in cr.fetchall():
        db_versions.append(ver[0])
    if set([x['md5sum'] for x in server_version]) - set(db_versions) - set([base_version]):
        return True
    return False

def do_upgrade(cr, pool):
    """Start upgrade process (called by login method and restore)"""
    versions = pool.get('sync_client.version')
    if versions is None:
        return True

    db_versions = versions.read(cr, 1, versions.search(cr, 1, [('state','=','installed')]), ['sum'])
    db_versions = map(lambda x:x['sum'], db_versions)
    server_lack_versions = set(db_versions) - set([x['md5sum'] for x in server_version])
    db_lack_versions = set([x['md5sum'] for x in server_version]) - set(db_versions) - set([base_version])

    if server_lack_versions:
        revision_ids = versions.search(cr, 1, [('sum','in',list(server_lack_versions))], order='date asc')
        res = do_prepare(cr, revision_ids)
        if res[0] == 'success':
            import tools
            os.chdir( tools.config['root_path'] )
            restart_server()
        else:
            return False

    elif db_lack_versions:
        base_module_upgrade(cr, pool, upgrade_now=True)
        # Note: There is no need to update the db versions, the `def init()' of the object do that for us

    return True

def reconnect_sync_server():
    """Reconnect the connection manager to the SYNC_SERVER if password file
    exists
    """
    import tools
    credential_filepath = os.path.join(tools.config['root_path'], 'unifield-socket.py')
    if os.path.isfile(credential_filepath):
        import pooler
        f = open(credential_filepath, 'r')
        lines = f.readlines()
        f.close()
        if lines:
            try:
                dbname = base64.decodestring(lines[0])
                password = base64.decodestring(lines[1])
                logger.info('dbname = %s' % dbname)
                db, pool = pooler.get_db_and_pool(dbname)
                db, pool = pooler.restart_pool(dbname) # do not remove this line, it is required to restart pool not to have
                # strange behaviour with the connection on web interface

                # do not execute this code on server side
                if not pool.get("sync.server.entity"):
                    cr = db.cursor()
                    # delete the credential file
                    os.remove(credential_filepath)
                    # reconnect to SYNC_SERVER
                    connection_module = pool.get("sync.client.sync_server_connection")
                    connection_module.connect(cr, 1, password=password)

                    # in caes of automatic patching, relaunch the sync
                    # (as the sync that launch the silent upgrade was aborted to do the upgrade first)
                    if connection_module.is_automatic_patching_allowed(cr, 1):
                        pool.get('sync.client.entity').sync_withbackup(cr, 1)
                    cr.close()
            except Exception as e:
                message = "Impossible to automatically re-connect to the SYNC_SERVER using credentials file : %s"
                logger.error(message % (unicode(e)))


def check_mako_xml():
    """
    read all xml and mako files to check that the tag ExpandedColumnCount is
    not present in it. This tag is useless and can lead to regression if the
    count change.
    """
    import tools
    logger.info("Check mako and xml files don't contain ExpandedColumnCount tag...")
    path_to_exclude = [os.path.join(tools.config['root_path'], 'backup')]
    for file_path in find(tools.config['root_path']):
        full_path = os.path.join(tools.config['root_path'], file_path)
        if not os.path.isfile(full_path):
            continue
        if full_path.endswith('.xml') or full_path.endswith('.mako'):
            excluded = False
            for exclusion in path_to_exclude:
                if exclusion in full_path:
                    excluded = True
                    break
            if excluded:
                continue
            with open(full_path, 'r') as file_to_check:
                line_number = 0
                for line in file_to_check:
                    line_number += 1
                    if 'ExpandedColumnCount' in line:
                        logger.warning('ExpandedColumnCount is present in file %s line %s.' % (full_path, line_number))
    logger.info("Check mako and xml files finished.")

#
# Functions related to upgrading PostgreSQL.
#

def _find_pg_patch():
    """
    Looks in the cwd for a file matching pgsql-*-*-patch.
    Returns the filename of the patch, the oldVer and the newVer.
    """
    import glob

    if os.path.isfile('pgsql-8.4.17-9.6.3-patch'):
        # ouch : this file should not be here
        warn('Deleting zombie pgsql-8.4.17-9.6.3-patch')
        os.remove('pgsql-8.4.17-9.6.3-patch')

    pfiles = glob.glob('pgsql-*-*-patch')
    pfiles.sort()
    if len(pfiles) == 0:
        return None, None, None

    if len(pfiles) == 2:
        (oldVer1, newVer1) = pfiles[0].split('-')[1:3]
        (oldVer2, newVer2) = pfiles[1].split('-')[1:3]
        if oldVer1 == '9.6.32' and oldVer2 == '9.6.33' and newVer1 == newVer2:
            try:
                with open(r'../pgsql/bin/psql.exe', 'rb') as f:
                    psql_exe_md5 = md5(f.read()).hexdigest()
                if psql_exe_md5 == '1ee9b41ee3f9d63816c5fc0f00862cbd':
                    # 9.6.3-2
                    _archive_patch(pfiles[1])
                    pfiles = [pfiles[0]]
                elif psql_exe_md5 == '8651954c8b170a2b2de004df446d6693':
                    # 9.6.3-3
                    _archive_patch(pfiles[0])
                    pfiles = [pfiles[1]]
                else:
                    warn("md5 %s does not match" % (psql_exe_md5,))
                    return None, None, None
            except:
                warn("Unable to compute md5 on ../pgsql/bin/psql.exe")
                return None, None, None
    if len(pfiles) != 1:
        warn("Too many PostgreSQL patch files: %s" % pfiles)
        warn("PostgreSQL will not be updated.")
        return None, None, None

    (oldVer, newVer) = pfiles[0].split('-')[1:3]

    # Check version format: 8.4.14 or 10.1
    if not re.match('\d+\.\d+(\.\d+)?', oldVer) or \
       not re.match('\d+\.\d+(\.\d+)?', newVer):
        return None, None, None

    return pfiles[0], oldVer, newVer

def _is_major(oldVer, newVer):
    oldVer = oldVer.split('.')
    newVer = newVer.split('.')
    if int(oldVer[0]) >= 10:
        # for 10.x and onward, second position indicates minor
        # version: https://www.postgresql.org/support/versioning/
        return oldVer[0] != newVer[0]
    if (oldVer[0] != newVer[0] or
            oldVer[0] == newVer[0] and oldVer[1] != newVer[1]):
        return True
    return False

def _no_log(*x):
    pass

def _archive_patch(pf):
    """
    Put away the patch file in order to indicate that it has
    already been applied and PG update should not be attempted
    again.
    """
    warn('Archiving patch file %s' % pf)
    if not os.path.exists('backup'):
        os.mkdir('backup')
    bf = os.path.join('backup', pf)
    if os.path.exists(bf):
        os.remove(bf)
    os.rename(pf, bf)

def do_pg_update():
    """
    This function is run on every server start (see openerp-server.py).
    If the conditions are not right for a PostgreSQL update, it
    immediately returns, so that the server can start up (the common case).
    If an update is required, then it attempts the update. If the
    update fails, it must leave the server in the same condition it
    started, i.e. with the original Postgres up and running.
    """
    # Postgres updates are only done on Windows.
    if os.name != "nt":
        return

    # We need to open this here because do_update only
    # opens it once it starts to work, not if there is no
    # update to apply.
    global log
    try:
        log = open(log_file, 'a')
    except Exception as e:
        log = sys.stderr
        warn("Could not open %s correctly: %s" % (log_file, e))

    # If there is no patch file available, then there's no
    # update to do.
    try:
        pf, oldVer, newVer = _find_pg_patch()
        if pf is None:
            return
    except Exception as e:
        warn("Error %s" % (e,))
        return

    try:
        with open(pf, 'rb') as f:
            pdata = f.read()
    except Exception as e:
        warn("Could not read patch file %s: %s" % (pf, e))
        _archive_patch(pf)
        return

    for root in ('c:\\', 'd:\\'):
        if os.path.exists(root):
            free = get_free_space_mb(root)
            if free < 1000:
                warn("Less than 1 gb free on %s. Not attempting PostgreSQL upgrade." % root)
                return

    is_major = _is_major(oldVer, newVer)
    # upgrade
    #
    # MAJOR ONLY: 0. find out if tablespaces are in use, if so abort
    # 1. figure out where the old PG is and copy it to pgsql-next
    # 2. patch pgsql-next, nuke patch file
    # MAJOR ONLY: 3. prepare new db dir using new initdb, old user/pass.
    # MAJOR ONLY: 3.5 Alter tables to work around a bug
    # MAJOR ONLY: 3.8: US-3506: remove any dependency on psql service
    # 4. stop server
    # MAJOR ONLY: 5. pg_upgrade -> if fail, clean db dir, goto 8
    # 6. commit to new bin dir, put it in '..\pgsql'
    # 7. if old was 8.4, change service entry
    # 8. start server
    # MAJOR ONLY: 9. Alter tables again to back out workaround

    warn("Postgres major update from %s to %s" % (oldVer, newVer))
    import tools

    stopped = False
    pg_new_db = None
    run_analyze = False
    re_alter = False
    failed = False
    try:
        env = os.environ
        if tools.config.get('db_user'):
            env['PGUSER'] = tools.config['db_user']
        if tools.config.get('db_password'):
            env['PGPASSWORD'] = tools.config['db_password']

        pg_new = r'..\pgsql-next'
        if oldVer == '8.4.17':
            svc = 'PostgreSQL_For_OpenERP'
            pg_old = r'D:\MSF data\Unifield\PostgreSQL'
        else:
            svc = 'Postgres'
            pg_old = r'..\pgsql'
        if not os.path.exists(pg_old):
            raise RuntimeError('PostgreSQL install directory %s not found.' % pg_old)

        pg_trash = r'..\psql_old_%s' % oldVer
        if os.path.exists(pg_trash):
            raise RuntimeError('%s directory exists, old aborted upgrade ?' % pg_trash)

        if is_major:
            # 0: check for tablespaces (pg_upgrade seems to unify them
            # into pg_default, which is not ok)
            cmd = [ os.path.join(pg_old, 'bin', 'psql'), '-t', '-c',
                    'select count(*) > 2 from pg_tablespace;', 'postgres' ]
            out = None
            try:
                out = subprocess.check_output(cmd, stderr=log, env=env)
            except subprocess.CalledProcessError as e:
                warn(e)
                warn("out is", out)
            if out is None or 'f' not in out:
                raise RuntimeError("User-defined tablespaces might be in use. Upgrade needs human intervention.")

        # 1: use old PG install to make a new one to patch
        if os.path.exists(pg_new):
            warn("Removing previous %s directory" % pg_new)
            shutil.rmtree(pg_new)

        if oldVer == '8.4.17':
            warn("Creating %s by selective copy from %s" % (pg_new, pg_old))
            os.mkdir(pg_new)
            for d in ('bin', 'lib', 'share'):
                shutil.copytree(os.path.join(pg_old, d),
                                os.path.join(pg_new, d))
        else:
            shutil.copytree(pg_old, pg_new)

        # 2: patch the pg exes -- no trial run here, because if applyPatch
        # fails, we have only left pg_new unusable, and we will revert
        # to pg_old. Compare to minor (in-place) upgrade, above.
        warn('Patching %s' % pg_new)
        bsdifftree.applyPatch(pdata, pg_new, log=warn)
        _archive_patch(pf)

        if is_major:
            # 3: prepare the new db
            pg_old_db = r'D:\MSF data\Unifield\PostgreSQL\data'
            if not os.path.exists(pg_old_db):
                raise RuntimeError('Could not find existing PostgreSQL data in %s' % pg_old_db)
            pg_new_db = pg_old_db + '-new'
            if os.path.exists(pg_new_db):
                raise RuntimeError('New data directory %s already exists.' % pg_new_db)
            pwf = tempfile.NamedTemporaryFile(delete=False)
            pwf.write(tools.config.get('db_password'))
            pwf.close()
            cmd = [ os.path.join(pg_new, 'bin', 'initdb.exe'),
                    '--pwfile', pwf.name,
                    '-A', 'md5',
                    '-U', tools.config.get('db_user'),
                    '--locale', 'English_United States',
                    '-E', 'UTF8', pg_new_db
                    ]
            warn('initdb: %r' % cmd)
            rc = subprocess.call(cmd, stdout=log, stderr=log, env=env)
            os.remove(pwf.name)
            if rc != 0:
                raise RuntimeError("initdb returned %d" % rc)

            # modify the postgresql.conf file for best
            # defaults
            pgconf = os.path.join(pg_new_db, "postgresql.conf")
            with open(pgconf, "a") as f:
                f.write("listen_addresses = 'localhost'\n")
                f.write("shared_buffers = 1024MB\n")

            # 3.5: Alter tables to work around
            # https://bugs.launchpad.net/openobject-server/+bug/782688
            cmd = [ os.path.join(pg_old, 'bin', 'psql'), '-A', '-t', '-c',
                    'select datname from pg_database where not datistemplate and datname != \'postgres\'', 'postgres' ]
            try:
                out = subprocess.check_output(cmd, stderr=log, env=env)
            except subprocess.CalledProcessError as e:
                warn("alter tables failed to get db list: %s" % e)
                out = ""
            dbs = out.split()

            cf = tempfile.NamedTemporaryFile(delete=False)
            for db in dbs:
                warn("alter tables in %s" % db)
                cf.write("\\connect \"%s\"\n alter table ir_actions alter column \"name\" drop not null;\n" % db)
            cf.close()
            cmd = [ os.path.join(pg_old, 'bin', 'psql'), '-f', cf.name, 'postgres' ]
            out = None
            try:
                out = subprocess.check_output(cmd, stderr=log, env=env)
            except subprocess.CalledProcessError as e:
                warn("problem running psql: %s" % e)
            warn("alter tables output is: ", out)
            os.remove(cf.name)
            re_alter = True

            # 3.8: US-3506: remove any dependency on psql service
            try:
                subprocess.call('sc config openerp-server-6.0 depend= ""', stdout=log, stderr=log)
            except OSError as e:
                warn('Trying to remove the service dependency gave error %s, continuing.'%e)

        # 4: stop old service
        subprocess.call('net stop %s' % svc, stdout=log, stderr=log)
        stopped = True

        if is_major:
            # 5: pg_upgrade
            cmd = [ os.path.join(pg_new, 'bin', 'pg_upgrade'),
                    '-b', os.path.join(pg_old, 'bin'),
                    '-B', os.path.join(pg_new, 'bin'),
                    '-d', pg_old_db, '-D', pg_new_db, '-k', '-v',
                    ]
            rc = subprocess.call(cmd, stdout=log, stderr=log, env=env)
            if rc != 0:
                raise RuntimeError("pg_upgrade returned %d" % rc)

            # The pg_upgrade went ok, so we are committed now. Nuke the
            # old db directory and move the upgraded one into place.
            warn("pg_upgrade returned %d, committing to new version" % rc)
            run_analyze = True

            warn("Rename %s to %s." % (pg_new_db, pg_old_db))
            # we do this with two renames since rmtree/rename sometimes
            # failed (why? due to antivirus still holding files open?)
            pg_old_db2 = pg_old_db + "-trash"
            os.rename(pg_old_db, pg_old_db2)
            os.rename(pg_new_db, pg_old_db)
            shutil.rmtree(pg_old_db2, True)

        # 6: commit to new bin dir
        if oldVer == '8.4.17':
            # Move pg_new to it's final name.
            os.rename(pg_new, r'..\pgsql')
            # For 8.4->9.9.x transition, nuke 8.4 install
            warn("Removing stand-alone PostgreSQL 8.4 installation.")
            cmd = [ os.path.join(pg_old, 'uninstall-postgresql.exe'),
                    '--mode', 'unattended',
                    ]
            rc = subprocess.call(cmd, stdout=log, stderr=log)
            warn("PostgreSQL 8.4 uninstall returned %d" % rc)
            pg_old = r'..\pgsql'
        else:
            warn("Rename %s to %s." % (pg_old, pg_trash))
            shutil.move(pg_old, pg_trash)
            warn("Rename done.")

            warn("Rename %s to %s." % (pg_new, pg_old))
            shutil.move(pg_new, pg_old)
            warn("Rename done.")

            try:
                warn("Remove %s." % pg_trash)
                shutil.rmtree(pg_trash)
                warn("Remove done.")
            except Exception as e:
                s = str(e) or type(e)
                warn('Unable to delete %s : %s', (pg_trash, s))


        pgp = os.path.normpath(os.path.join(pg_old, 'bin'))
        if tools.config['pg_path'] != pgp:
            warn("Setting pg_path to %s." % pgp)
            tools.config['pg_path'] = pgp
            tools.config.save()
        else:
            warn("pg_path is correct")

        # 7: change service entry to the correct install location
        if oldVer == '8.4.17':
            cmd = [
                os.path.join(pg_old, 'bin', 'pg_ctl'),
                'register', '-N', 'Postgres',
                '-U', 'openpgsvc',
                '-P', '0p3npgsvcPWD',
                '-D', pg_old_db,
            ]
            rc = subprocess.call(cmd, stdout=log, stderr=log)
            if rc != 0:
                raise RuntimeError("pg_ctl returned %d" % rc)
            svc = 'Postgres'

    except Exception as e:
        failed = True
        s = str(e) or type(e)
        warn(u'Failed to update Postgres', s)
    finally:
        try:
            if pg_new_db is not None and os.path.exists(pg_new_db):
                warn("Removing failed DB upgrade directory %s" % pg_new_db)
                shutil.rmtree(pg_new_db)
        except Exception:
            # don't know what went wrong, but we must not crash here
            # or else OpenERP-Server will not start.
            pass
        # 8. start service (either the old one or the new one)
        if stopped:
            warn('Starting service %s' % svc)
            subprocess.call('net start %s' % svc, stdout=log, stderr=log)

        # 9. re-alter tables to put the problematic constraint back on
        if re_alter:
            cf = tempfile.NamedTemporaryFile(delete=False)
            for db in dbs:
                warn("alter tables in %s" % db)
                cf.write("\\connect \"%s\"\n alter table ir_actions alter column \"name\" set not null;\n" % db)
            cf.close()
            cmd = [ os.path.join(pg_old, 'bin', 'psql'), '-f', cf.name, 'postgres' ]
            out = None
            try:
                out = subprocess.check_output(cmd, stderr=log, env=env)
            except subprocess.CalledProcessError as e:
                warn("problem running psql: %s" % e)
            warn("re-alter tables output is: ", out)
            os.remove(cf.name)

        if run_analyze:
            cmd = [ os.path.join(r'..\pgsql', 'bin', 'vacuumdb'),
                    '--all', '--analyze-only' ]
            subprocess.call(cmd, stdout=log, stderr=log, env=env)

        if not failed:
            warn("Update done.")
    return

# https://stackoverflow.com/questions/51658/cross-platform-space-remaining-on-volume-using-python
def get_free_space_mb(dirname):
    """Return folder/drive free space (in megabytes)."""
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(dirname), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value / 1024 / 1024
    else:
        st = os.statvfs(dirname)
        return st.f_bavail * st.f_frsize / 1024 / 1024

#
# Unit tests follow
#
if __name__ == '__main__':
    d = tempfile.mkdtemp()
    os.chdir(d)

    # no file
    pf, oldVer, newVer = _find_pg_patch()
    assert pf == None

    # one good file
    with open('pgsql-8.4.17-9.6.3-patch', 'wb') as f:
        f.write('Fake patch for testing.')
    pf, oldVer, newVer = _find_pg_patch()
    assert oldVer == '8.4.17'
    assert newVer == '9.6.3'
    assert pf == 'pgsql-8.4.17-9.6.3-patch'

    # two files: oops
    warn("Expect 2 messages on stderr after this:")
    with open('pgsql-wat-huh-patch', 'wb') as f:
        f.write('Second fake patch for testing.')
    pf, oldVer, newVer = _find_pg_patch()
    assert pf == None

    # one file with wrong version format
    os.remove('pgsql-8.4.17-9.6.3-patch')
    pf, oldVer, newVer = _find_pg_patch()
    assert pf == None

    assert _is_major('8.4.17', '9.6.3')
    assert not _is_major('8.4.16', '8.4.17')
    assert _is_major('9.5.6', '9.6.3')
    assert _is_major('9.6.9', '10.1')
    assert not _is_major('10.1', '10.2')
    assert _is_major('21.9', '22.1')

    os.chdir('..')
    shutil.rmtree(d)
    root = "D:\\"
    if sys.platform != 'win32':
        root = '/'
    assert get_free_space_mb(root) != None
