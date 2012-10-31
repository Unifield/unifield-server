from __future__ import with_statement
import re
import os
import sys
from hashlib import md5
from datetime import datetime
from base64 import b64decode
from StringIO import StringIO
import logging

if sys.version_info >= (2, 6, 6):
    from zipfile import ZipFile, ZipInfo
else:
    from zipfile266 import ZipFile, ZipInfo

__all__ = ['server_version', 'server_version_file', 'parse_version_file', 'get_server_version', 'add_versions', 'new_version_file', \
           'do_update', 'update_path', 'lock_file', 'update_dir', 'log_file', 'base_version', 'do_upgrade', 'restart_required']

restart_required = False
## Warning: we expect to be in the bin/ directory to proceed!!
log_file = 'updater.log'
lock_file = 'update.lock'
update_dir = '.update'
server_version_file = 'unifield-version.txt'
new_version_file = os.path.join(update_dir, 'update-list.txt')

md5hex_size = (md5().digest_size * 8 / 4)
base_version = '8' * md5hex_size
re_version = re.compile(r'^\s*([a-fA-F0-9]{'+str(md5hex_size)+r'}\b)')

## Set the lock file to make OpenERP run into do_update method against normal execution
def set_lock(file=None):
    if file is None: file = lock_file
    with open(file, "w") as f:
        f.write(os.getcwd())

## Remove the lock
def unset_lock(file=None):
    global exec_path
    if file is None: file = lock_file
    with open(file, "r") as f:
        exec_path = f.read().strip()
    os.unlink(file)

## Short method to parse a "version file"
## Basically, a file where each line starts with the sum of a patch
def parse_version_file(filepath):
    assert os.path.isfile(filepath), "The file `%s' must be a file!" % filepath
    versions = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.rstrip()
            if not line: continue
            try:
                m = re_version.match(line)
                versions.append( m.group(1) )
            except AttributeError:
                raise Exception("Unable to parse version from file `%s': %s" % (filepath, line))
    return versions

## Autocmatically get the current versions of the server
def get_server_version():
    ## Get a special key 88888888888888888888888888888888 for default value if no server version can be found
    if not os.path.exists(server_version_file):
        return [base_version]
    return parse_version_file(server_version_file)

## Set server version with new versions
def add_versions(versions, filepath=server_version_file):
    if not versions:
        return
    with open(filepath, 'a') as f:
        for ver in versions:
            f.write((" ".join([unicode(x) for x in ver]) if hasattr(ver, '__iter__') else ver)+"\n")

## Unix-like find
def find(path):
    files = os.listdir(path)
    for name in iter(files):
        abspath = path+os.path.sep+name
        if os.path.isdir( abspath ) and not os.path.islink( abspath ):
            files.extend( map(lambda x:name+os.path.sep+x, os.listdir(abspath)) )
    return files

## Python free rmtree
def rmtree(files, path=None, verbose=False):
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

## Define way to forward logs
def warn(*args):
    global log
    log.write(("[%s] UPDATER: " % now())+" ".join(map(lambda x:unicode(x), args))+"\n")

## Try...Resume...
def Try(command):
    try:
        command()
    except BaseException, e:
        warn(unicode(e))
        return False
    else:
        return True


## Just like -u base / -u all
def base_module_upgrade(cr, pool, upgrade_now=False):
    modules = pool.get('ir.module.module')
    base_ids = modules.search(cr, 1, [('name', '=', 'base')])
    modules.button_upgrade(cr, 1, base_ids)
    if upgrade_now:
        pool.get('base.module.upgrade').upgrade_module(cr, 1, [])


## Real update of the server (before normal OpenERP execution)
def do_update():
    if os.path.exists(lock_file) and Try(unset_lock):
        global log
        ## Move logs log file
        try:
            log = open(log_file, 'a')
        except BaseException, e:
            log.write("Cannot write into `%s': %s" % (log, unicode(e)))
        warn(lock_file, 'removed')
        ## Now, update
        application_time = now()
        revisions = []
        files = None
        ## Remove any -d and -u flags from command-line parameters
        args = list(sys.argv)
        for i, x in enumerate(args):
            if x in ('-d', '-u'):
                args[i] = None
                args[i+1] = None
        args = filter(lambda x:x is not None, args)
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
            ## Update Files
            warn("Updating...")
            for f in files:
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
            add_versions([(x, application_time) for x in revisions])
            warn("Update successful.")
            warn("Revisions added: ", ", ".join(revisions))
            ## No database update here. I prefered to set modules to update just after the preparation
            ## The reason is, when pool is populated, it will starts by upgrading modules first
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
        warn(("Restart OpenERP in %s:" % exec_path), \
             [sys.executable]+args)
        if log is not sys.stderr:
            log.close()
        os.chdir(exec_path)
        os.execv(sys.executable, [sys.executable] + args)


## If server starts normally, this step will fix the paths with the configured path in config rc
def update_path():
    from tools import config
    for v in ('log_file', 'lock_file', 'update_dir', 'server_version_file', 'new_version_file'):
        globals()[v] = os.path.join(config['root_path'], globals()[v])
    global server_version
    server_version = get_server_version()


## Prepare patches for an upgrade of the server
def do_prepare(cr, revision_ids):
    if not revision_ids:
        return ('failure', 'Nothing to do.', {})
    import pooler
    pool = pooler.get_pool(cr.dbname)
    version = pool.get('sync_client.version')
    logger = logging.getLogger('updater')

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
    for rev in version.browse(cr, 1, revision_ids):
        # Check presence of the patch
        if not rev.patch:
            missing.append( rev )
            continue
        # Check if the file match the expected sum
        patch = b64decode( rev.patch )
        local_sum = md5(patch).hexdigest()
        if local_sum != rev.sum:
            corrupt.append( rev )
        elif not (corrupt or missing):
            # Extract the Zip
            f = StringIO(patch)
            try:
                zip = ZipFile(f, 'r')
                zip.extractall(path)
            finally:
                f.close()
            # Store to list of updates
            new_revisions.append( (rev.sum, ("[%s] %s - %s" % (rev.importance, rev.date, rev.name))) )
            # Fix the flag of the pending patches
            version.write(cr, 1, rev.id, {'state':'need-restart','applied':now()})
    # Restore patch states when error occurs
    if missing or corrupt:
        version.write(cr, 1, revision_ids, {'state':'not-installed'})
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
    # Make a lock file to make OpenERP able to detect an update
    set_lock()
    add_versions(new_revisions, new_version_file)
    message = "Server update prepared. Need to restart to complete the upgrade."
    logger.info(message)
    return ('success', message, {})


## Start upgrade process (typically called by login method and restore)
def do_upgrade(dbname):
    import tools
    import pooler
    cr = pooler.get_db(dbname).cursor()
    pool = pooler.get_pool(dbname)
    versions = pool.get('sync_client.version')
    if versions is None:
        return True

    db_versions = versions.read(cr, 1, versions.search(cr, 1, [('state','=','installed')]), ['sum'])
    db_versions = map(lambda x:x['sum'], db_versions)
    server_lack_versions = set(db_versions) - set(server_version)
    db_lack_versions = set(server_version) - set(db_versions) - set([base_version])

    if server_lack_versions:
        revision_ids = versions.search(cr, 1, [('sum','in',list(server_lack_versions))])
        res = do_prepare(cr, revision_ids)
        if res[0] == 'success':
            os.chdir( tools.config['root_path'] )
            global restart_required
            restart_required = True
        return False

    elif db_lack_versions:
        base_module_upgrade(cr, pool, upgrade_now=True)
        cr.commit()
        # Note: There is no need to update the db versions, the `def init()' of the object do that for us

    return True

