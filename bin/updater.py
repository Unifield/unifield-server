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

## Define way to forward logs
def warn(*args):
    sys.stderr.write(" ".join(map(lambda x:str(x), args))+"\n")

## Try...Resume...
def Try(command):
    try:
        command()
    except:
        e, msg = sys.exc_info()[0].__name__, str(sys.exc_info()[1])
        warn(str(msg))
        return False
    else:
        return True

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

def do_update():
## We expect to be in the bin/ directory to proceed
    if os.path.exists('update.lock'):
        rev_file = os.path.join('.update','revisions.txt')
        hist_file = "revision_history.txt"
        infos = {'exec_path':os.getcwd()}
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
                rmtree('backup')
            ## Update Files
            warn("Updating...")
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
                        warn("`%s' -> `%s'" % (f, bak))
                        os.rename(f, bak)
                    warn("`%s' -> `%s'" % (target, f))
                    os.rename(target, f)
            ## Update installed revisions in DB
            cur.execute("""UPDATE sync_client_version SET state = 'installed', applied = '%s' WHERE name in (%s)"""
                % ( datetime.today().strftime("%Y-%m-%d %H:%M:%S"), revisions ))
            warn("Update successful.")
            warn("Revisions added: ", ", ".join( infos['revisions'] ))
            args.extend(['-d', infos['dbname'], '-u', 'all'])
        except:
            warn("Update failure!")
            ## Update DB to mark revisions as not-installed
            if cur and infos:
                Try(lambda:cur.execute("""UPDATE sync_client_version SET state = 'not-installed' WHERE name in (%s)"""
                    % ( revisions )))
            ## Restore backup and purge .update
            if files:
                warn("Restoring...")
                for f in reversed(files):
                    target = os.path.join('backup', f)
                    if os.path.isfile(target) or os.path.islink(target):
                        warn("`%s' -> `%s'" % (target, f))
                    elif os.path.isdir(target):
                        warn("rmdir", target)
                        os.rmdir( target )
                warn("Purging...")
                Try(lambda:rmtree(files, '.update'))
                warn("rmdir", '.update')
                Try(lambda:os.rmdir( '.update' ))
        finally:
            if cur: cur.close()
            if conn: conn.close()
        ## Remove lock file
        warn("rm", 'update.lock')
        Try(lambda:os.unlink( 'update.lock' ))
        warn("Restart OpenERP in", infos['exec_path'], "with:",args)
        if infos: os.chdir(infos['exec_path'])
        os.execv(sys.executable, [sys.executable] + args)


