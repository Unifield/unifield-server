import sys
import os
from osv import osv, fields
import tools
from tools import config
from StringIO import StringIO
from base64 import b64decode
from hashlib import md5
#import logging

if sys.version_info >= (2, 6, 6):
    from zipfile import ZipFile, ZipInfo
else:
    from zipfile266 import ZipFile, ZipInfo

## Unix-like find
def find(path):
    files = os.listdir(path)
    for name in iter(files):
        abspath = path+os.path.sep+name
        if os.path.isdir( abspath ) and not os.path.islink( abspath ):
            files.extend( map(lambda x:name+os.path.sep+x, os.listdir(abspath)) )
    return files

class upgrade(osv.osv_memory):
    _name = 'sync_client.upgrade'
    _description = "OpenERP Upgrade Wizard"

    #__logger = logging.getLogger('sync.client')

    def restart(self, cr, uid, ids, context=None):
        os.chdir( config['root_path'] )
        tools.restart_required = True
        return  {'type': 'ir.actions.act_window_close'}

    def download(self, cr, uid, ids, context=None):
        """Downlad the patch to fill the version record"""
        ## TODO all revisions at once? wait MSF
        revisions = self.pool.get('sync_client.version')
        next_revisions = revisions._get_next_revisions(cr, uid, context=context)
        if not next_revisions:
            raise osv.except_osv("Error!", "Nothing to do.")
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        uuid = self.pool.get('sync.client.entity').get_uuid(cr, uid)
        text = "These patches has been downloaded and are ready to install:\n\n"
        for rev in revisions.browse(cr, uid, next_revisions, context=context):
            text += "- [%s] %s (%s at %s)\n" % (rev.importance, rev.name, rev.sum, rev.date, )
            if not rev.patch:
                patch = proxy.get_zip( uuid, rev.sum )
                if not patch[0]:
                    raise osv.except_osv("Error!", "Can't retrieve the patch %s (%s)!" % (rev.name, rev.sum))
                revisions.write(cr, uid, rev.id, {'patch':patch[1]})
                cr.commit()
        return self.write(cr, uid, ids, {
            'message' : text,
            'state' : 'need-install',
        }, context=context)

    def do_upgrade(self, cr, uid, ids, context=None):
        """Actualy, prepare the upgrade to be done at server restart"""
        ## Check if revision upgrade applies
        next_state = self._get_state(cr, uid, context=context)
        if next_state != 'need-install':
            message = "Cannot install now.\n\n"
            message += self._generate(cr, uid, context=context)
            return self.write(cr, uid, ids, {
                'message' : message,
                'state' : next_state,
            }, context=context)
        revisions = self.pool.get('sync_client.version')
        next_revisions = revisions._get_next_revisions(cr, uid, context=context)
        ## Make an update temporary path
        path = os.path.join(config['root_path'], ".update")
        if not os.path.exists(path):
            os.mkdir(path)
        else:
            for f in reversed(find(path)):
                target = os.path.join(path, f)
                if os.path.isfile(target) or os.path.islink(target):
                    print "rm", target
                    os.unlink( target )
                elif os.path.isdir(target):
                    print "rmdir", target
                    os.rmdir( target )
        if not (os.path.isdir(path) and os.access(path, os.W_OK)):
            return self.write(cr, uid, ids, {
                'message' : "The path `%s' is not a dir or is not writable!" % path,
            }, context=context)
        ## Proceed all patches
        new_revisions = list()
        for rev in revisions.browse(cr, uid, next_revisions, context=context):
            ## Check if the file match the expected sum
            patch = b64decode( rev.patch )
            local_sum = md5(patch).hexdigest()
            if local_sum != rev.sum:
                return self.write(cr, uid, ids, {
                    'message' : "The file you downloaded seems to be corrupt.\nLocal sum: %s\nDistant sum: %s\n\nPlease download it again." % (local_sum, rev.sum),
                    'state' : 'need-download',
                }, context=context)
            ## Extract the Zip
            f = StringIO(patch)
            try:
                zip = ZipFile(f, 'r')
                zip.extractall(path)
            finally:
                f.close()
            ## Store to list of updates
            new_revisions.append( rev.name )
            ## Fix the flag of the pending revisions
            revisions.write(cr, uid, rev.id, {'state':'need-restart'}, context=context)
        ## Make a lock file to make OpenERP able to detect an update
        f = open(os.path.join(config['root_path'], "update.lock"), "w")
        f.write(str({
            'dbname' : cr.dbname,
            'revisions' : new_revisions,
            'db_user' : config['db_user'] or None, ## Note that False values are not acceptable for psycopg
            'db_host' : config['db_host'] or None,
            'db_port' : config['db_port'] or None,
            'db_password' : config['db_password'] or None,
            'exec_path' : os.getcwd(),
        }))
        f.close()
        ## Refresh the window
        self.write(cr, uid, ids, {
            'message' : self._generate(cr, uid, context=context),
            'state' : 'need-restart',
        }, context=context)
        ## Restart automatically
        cr.commit()
        return self.restart(cr, uid, ids, context=context)

    def _generate(self, cr, uid, context=None):
        """Make the wizard caption"""
        me = self.pool.get('sync.client.entity').get_entity(cr, uid, context)
        if me.is_syncing:
            return "Blocked during synchro.\n\nPlease try again later."
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return "OpenERP needs to be restart to complete the installation."
        text = ""
        currev = revisions._get_last_revision(cr, uid, context=context)
        if currev:
            text += "The current revision is %s (%s at %s) and has been applied at %s.\n" % (currev.name, currev.sum, currev.date, currev.applied)
        else:
            text += "No revision has been applied yet.\n"
        next_revisions = revisions._get_next_revisions(cr, uid, context=context)
        if next_revisions:
            text += "\n"
            if len(next_revisions) == 1:
                text += "There is 1 revision available.\n"
            else:
                text += "There are %s revisions available.\n" % len(next_revisions)
            for rev in revisions.browse(cr, uid, next_revisions):
                text += "- [%s] %s (%s at %s)\n" % (rev.importance, rev.name, rev.sum, rev.date, )
        else:
            text += "\nYour OpenERP version is up-to-date.\n"
        return text

    def _get_state(self, cr, uid, context=None):
        me = self.pool.get('sync.client.entity').get_entity(cr, uid, context)
        if me.is_syncing:
            return 'blocked'
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return 'need-restart'
        next_revisions = revisions._get_next_revisions(cr, uid, context=context)
        if not next_revisions:
            return 'up-to-date'
        if not revisions._is_update_available(cr, uid, next_revisions, context=context):
            return 'need-download'
        return 'need-install'

    _columns = {
        'message' : fields.text("Caption", readonly=True),
        'state' : fields.selection([('need-download','Need Download'),('up-to-date','Up-To-Date'),('need-install','Need Install'),('need-restart','Need Restart'),('blocked','Blocked')], string="Status"),
    }

    _defaults = {
        'message' : _generate,
        'state' : _get_state,
    }

upgrade()

