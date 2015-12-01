"""
Unifield module to upgrade the instance to a next version of Unifield
Beware that we expect to be in the bin/ directory to proceed!!
"""
from __future__ import with_statement
import re
import os
import sys
from hashlib import md5
from datetime import datetime
from base64 import b64decode
from StringIO import StringIO
import logging
import time

if sys.version_info >= (2, 6, 6):
    from zipfile import ZipFile, ZipInfo
else:
    from zipfile266 import ZipFile, ZipInfo

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

# match 4 groups : md5sum <space> date (yyyy-mm-dd) <space> time (hh:mm:ss) <space> version
#example : 694d9c65bce826551df26cefcc6565e1 2015-11-27 16:15:00 UF2.0rc3
re_version = re.compile(r'^\s*([a-fA-F0-9]{'+str(md5hex_size)+r'}\b)\s*(\d+-\d+-\d+)\s*(\d+:\d+:\d+)\s*(.*)')
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
    versions_dict = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.rstrip()
            if not line: continue
            try:
                result = re_version.findall(line)
                if not result: continue
                md5sum, date, time, version_name = result[0]
                versions_dict[md5sum] = {'date': date,
                                         'time': time,
                                         'version_name': version_name,
                                         }
            except AttributeError:
                raise Exception("Unable to parse version from file `%s': %s" % (filepath, line))
    return versions_dict

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
    if path is None and isinstance(files, str):
        path, files = files, find(files)
    for f in reversed(files):
        target = os.path.join(path, f) if path is not None else f
        if os.path.isfile(target) or os.path.islink(target):
            warn("unlink", target)
            os.unlink( target )
        elif os.path.isdir(target):
            warn("rmdir", target)
            os.rmdir( target )

def now():
    return datetime.today().strftime("%Y-%m-%d %H:%M:%S")

log = sys.stderr

def warn(*args):
    """Define way to forward logs"""
    global log
    log.write(("[%s] UPDATER: " % now())+" ".join(map(lambda x:unicode(x), args))+os.linesep)
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
        revisions = {}
        files = None
        try:
            ## Revisions that going to be installed
            revisions = parse_version_file(new_version_file)
            os.unlink(new_version_file)
            ## Explore .update directory
            files = find(update_dir)

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

                res = re.match("^(.*)\\service\\libs\\servicemanager.pyd", regval)
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
            for f in files:
                webfile = re.match("^web[\\\/](.*)", f)
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
            add_versions([(md5, data_dict['date'],
                           data_dict['time'],
                           data_dict['version_name']) for md5, data_dict in revisions_dict.items()])
            warn("Update successful.")
            warn("Revisions added: ", ", ".join(revisions_dict.keys()))
            ## No database update here. I preferred to set modules to update just after the preparation
            ## The reason is, when pool is populated, it will starts by upgrading modules first

            #Restart web server
            if webupdated and os.name == "nt":
                try:
                    import subprocess
                    retcode = subprocess.call('net stop "OpenERP Web 6.0"')
                    retcode = subprocess.call('net start "OpenERP Web 6.0"')
                except OSError, e:
                    warn("Exception in Web server restart :")
                    warn(unicode(e))

        except BaseException, e:
            warn("Update failure!")
            warn(unicode(e))
            ## Restore backup and purge .update
            if files:
                warn("Restoring...")
                for f in reversed(files):
                    target = os.path.join('backup', f)
                    if os.path.isfile(target) or os.path.islink(target):
                        warn("`%s' -> `%s'" % (target, f))
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
            f = StringIO(patch)
            try:
                zip = ZipFile(f, 'r')
                zip.extractall(path)
            finally:
                f.close()
            # Store to list of updates
            new_revisions.append( (rev.sum, ("[%s] %s - %s - %s" % (rev.importance, rev.date, rev.name, rev.version_name))) )
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
    # Fix the flag of the pending patches
    version.write(cr, 1, need_restart, {'state':'need-restart'})
    # Make a lock file to make OpenERP able to detect an update
    set_lock()
    add_versions(new_revisions, new_version_file)
    logger.info("Server update prepared. Need to restart to complete the upgrade.")
    return ('success', 'Restart required', {})

def dump_db(cr, pool):
    bck_obj = pool.get('backup.config')
    if bck_obj:
        # test if column exists
        cr.execute("SELECT attr.attname FROM pg_attribute attr, pg_class class WHERE attr.attrelid = class.oid AND class.relname = 'backup_config' AND attr.attname='beforepatching'")
        if cr.fetchall():
            bck_obj.exp_dump_for_state(cr, 1, 'beforepatching')

def test_do_upgrade(cr):
    cr.execute("select count(1) from pg_class where relkind='r' and relname='sync_client_version'")
    if not cr.fetchone()[0]:
        return False

    cr.execute("select sum from sync_client_version where state='installed'")
    db_versions = []
    for ver in cr.fetchall():
        db_versions.append(ver[0])
    if set(server_version) - set(db_versions) - set([base_version]):
        return True
    return False

def do_upgrade(cr, pool):
    """Start upgrade process (called by login method and restore)"""
    versions = pool.get('sync_client.version')
    if versions is None:
        return True

    db_versions = versions.read(cr, 1, versions.search(cr, 1, [('state','=','installed')]), ['sum'])
    db_versions = map(lambda x:x['sum'], db_versions)
    server_lack_versions = set(db_versions) - set(server_version)
    db_lack_versions = set(server_version) - set(db_versions) - set([base_version])

    if server_lack_versions:
        revision_ids = versions.search(cr, 1, [('sum','in',list(server_lack_versions))], order='date asc')
        res = do_prepare(cr, revision_ids)
        if res[0] == 'success':
            try:
                dump_db(cr, pool)
            except Exception, e:
                logger.error('Can\'t create backup before patching: %s' % (unicode(e),))
            import tools
            os.chdir( tools.config['root_path'] )
            restart_server()
        else:
            return False

    elif db_lack_versions:
        try:
            dump_db(cr, pool)
        except Exception, e:
            logger.error('Can\'t create backup before patching: %s' % (unicode(e),))
        base_module_upgrade(cr, pool, upgrade_now=True)
        # Note: There is no need to update the db versions, the `def init()' of the object do that for us

    return True
