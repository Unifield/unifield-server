'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
from tools.translate import _
from updater import base_version, server_version, isset_lock
import calendar
import time
import logging
from tools import config
import os
import hashlib
from io import StringIO
import tarfile
from base64 import b64decode, b64encode

IMPORT_PATCH_SUCCESS, \
    IMPORT_PATCH_INVALID, \
    IMPORT_PATCH_UNKNOWN, \
    IMPORT_PATCH_IGNORED, \
    = list(range(4))

class version(osv.osv):

    _name = "sync_client.version"

    def _patch_needs_to_be_downloaded(self, cr, uid, ids, name, args, context=None):
        cr.execute("""\
            SELECT id, patch IS NULL and coalesce(patch_path, '')='' FROM %s WHERE id IN %%s""" % self._table, [tuple(ids)])  # not_a_user_entry
        return dict(cr.fetchall())

    _columns = {
        'name' : fields.char(string='Version', size=256, readonly=True),
        'patch' : fields.binary('Patch', readonly=True),
        'sum' : fields.char(string="Commit Hash", size=256, required=True, readonly=True),
        'date' : fields.datetime(string="Revision Date", readonly=True),
        'comment' : fields.text("Comment", readonly=True),
        'state' : fields.selection([('not-installed','Not Installed'),('need-restart','Need Restart'),('installed','Installed')], string="State", readonly=True),
        'applied' : fields.datetime("Applied", readonly=True),
        'importance' : fields.selection([('required','Required'),('optional','Optional')], "Importance Flag", readonly=True),
        'need_download' : fields.function(_patch_needs_to_be_downloaded,
                                          type='boolean', method=True, readonly=True),
        'patch_path': fields.char('Patch stored on filesystem', size=256),
    }

    _defaults = {
        'state' : 'not-installed',
    }

    _sql_constraints = [
        ('unique_sum', 'unique(sum)', "Patches must be unique!"),
        ('sync_client_version_applied_check', '''check (state = 'installed' and applied is not null or state != 'installed')''', "Patches marked as 'installed' must have an application date"),
        ('sync_client_version_date_check', '''check (state = 'not-installed' and date is not null or state != 'not-installed')''', "Patches marked as 'not-installed' must have an emission date"),
    ]

    _logger = logging.getLogger('update_client')


    def init(self, cr):
        try:
            now = fields.datetime.now()
            current_versions = self.read(cr, 1, self.search(cr, 1, []), ['id','sum','state'])
            versions_id = dict([(x['sum'], x['id']) for x in current_versions])
            current_versions.append( {'sum':base_version,'state':'installed'} )
            # Create non-existing versions in db
            server_version_keys = [x['md5sum'] for x in server_version]
            for rev in set(server_version_keys) - set([x['sum'] for x in current_versions]):
                for s_ver in server_version:
                    if rev == s_ver['md5sum']:
                        versions_id[rev] = self.create(cr, 1,
                                                       {'sum':rev,
                                                        'state':'installed',
                                                        'applied':now,
                                                        'version':version,
                                                        'name':s_ver['name'],
                                                           'date':s_ver['date']})
                        break
            # Update existing ones
            self.write(cr, 1, [x['id'] for x in current_versions \
                               if x['sum'] in server_version_keys and not x['state'] == 'installed'], \
                       {'state':'installed','applied':now})
            # Set last revision (assure last update has the last applied date)
            time.sleep(1)
            if len(server_version_keys) > 1:
                self.write(cr, 1, [versions_id[server_version_keys[-1]]], {'applied':fields.datetime.now()})
        except BaseException:
            self._logger.exception("version init failure!")

    def get_patch_folder(self, cr):
        folder = os.path.join(config['root_path'], '..', 'Patches', cr.dbname)
        if not os.path.exists(folder):
            os.makedirs(folder)
        return folder

    def get_patch_file(self, cr, uid, id, context=None):
        return os.path.join(self.get_patch_folder(cr), '%s.zip' % id)

    def _need_restart(self, cr, uid, context=None):
        return isset_lock()

    def _update(self, cr, uid, revisions, context=None):
        res = []
        for rev in revisions:
            ids = self.search(cr, uid, [('sum','=',rev['sum'])], limit=1, context=context)
            if not ids:
                res.append( self.create(cr, uid, rev, context=context) )
            elif self.browse(cr, uid, ids, context=context)[0].state == 'not-installed':
                self.write(cr, uid, ids, rev, context=context)
                res.extend( ids )
        return res

    def _get_last_revision(self, cr, uid, context=None):
        rev_ids = self.search(cr, uid, [('state','=','installed')], limit=1, order='applied desc, id desc', context=context)
        return self.browse(cr, uid, rev_ids[0]) if rev_ids else False

    def _get_next_revisions(self, cr, uid, context=None):
        return self.search(cr, uid, [('state','!=','installed')], order='date asc')

    def _is_outdated(self, cr, uid, force_recalculate=False, exact_version=False, context=None):
        if hasattr(self, 'version_check') and not force_recalculate:
            return bool(self.version_check)
        current = self._get_last_revision(cr, uid, context=context)
        where = [('state','!=','installed')]
        if exact_version:
            where.append(('importance','=','required'))
        if current and current.date:
            where.append(('date','>',current.date))
        self.version_check = self.search(cr, uid, where, limit=1)
        return bool(self.version_check)

    def _is_update_available(self, cr, uid, ids, context=None):
        for id in ids if isinstance(ids, list) else [ids]:
            rev = self.browse(cr, uid, id, context=context)
            if not rev.patch and not rev.patch_path:
                return False
        return True

    def search_installed_since(self, cr, uid, since_date, context=None):
        """
        Search installed patches since given date.
        """
        return self.search(cr, uid,
                           [('state','=','installed'),('applied','>',since_date)],
                           context=context)

    def import_patch(self, cr, uid, patch=None, decoded=None, context=None):
        """import patch file or tarball of patch files by providing a base64 encoded string or the decoded string"""
        if decoded is None:
            decoded = b64decode(patch)
        elif patch is None:
            patch = b64encode(decoded)
        else:
            raise AssertionError("You must provide at least and at most one of these arguments: patch, decoded")
        if not decoded[:2] == 'PK': return IMPORT_PATCH_INVALID
        patch_sum = hashlib.md5(decoded).hexdigest()
        ids = self.search(cr, uid, [('sum','=',patch_sum)], context=context)
        if not ids: return IMPORT_PATCH_UNKNOWN
        info = self.browse(cr, uid, ids, context=context)[0]
        if info.state == 'installed' or not info.need_download: return IMPORT_PATCH_IGNORED
        self.write(cr, uid, ids, {'patch':patch}, context=context)
        self._logger.info("Patch %(name)s (%(sum)s) successfuly imported" % info)
        return IMPORT_PATCH_SUCCESS

    def export_patch(self, cr, uid, ids, action_on_missing='warn', context=None):
        """export patches of ids given to a single tarball string base64 encoded"""
        if not ids: return False
        missing = []
        tar_fh = StringIO()
        tar = tarfile.TarFile(fileobj=tar_fh, mode='w')
        for rec in self.browse(cr, uid, ids, context=context):
            if not rec.patch:
                missing.append(rec)
                if action_on_missing == 'warn':
                    self._logger.warn("The patch sum %(sum)s (id=%(id)d) is missing in the database!" % rec)
                continue
            if missing and action_on_missing == 'raise': continue
            patch_fh = StringIO(b64decode(rec.patch))
            tar_info = tarfile.TarInfo(rec.sum + ".zip")
            tar_info.mtime = calendar.timegm(time.gmtime())
            tar_info.size = patch_fh.len
            tar.addfile(tar_info, patch_fh)
        tar.close()
        tar_fh.seek(0)
        if action_on_missing == 'raise' and missing:
            raise osv.except_osv(_("Error!"),
                                 _("Can not find patches for revisions:") + ' ' +
                                 ", ".join(["%(sum)s (id=%(id)d)" % rec for rec in missing]))
        return b64encode(tar_fh.read())

    _order = 'date desc'

version()

class entity(osv.osv):
    _inherit = "sync.client.entity"

    _columns = {
        'user_rights_name': fields.char('UR Version', size=256),
        'user_rights_sum': fields.char('UR Sum', size=256),
        'user_rights_state': fields.selection([('installed', 'Installed'), ('to_install', 'To install')], 'UR State'),
        'user_rights_data': fields.binary('UR Zip file'),
        'current_user_rights_name': fields.char('Installed UR Version', size=256, readonly=1),
    }

    def get_upgrade_status(self, cr, uid, context=None):
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return _("OpenERP is restarting<br/>to finish upgrade...")
        if revisions._is_outdated(cr, uid, context=context):
            return _("Major upgrade is available.<br/>The synchronization process is disabled<br/>while the instance is not upgraded.")
        return ""

    def upgrade(self, cr, uid, context=None):
        self.pool.get('sync.client.sync_server_connection').connect(cr, uid, context=context)
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return (False, "Need restart")
        current_revision = revisions._get_last_revision(cr, uid, context=context)
        if current_revision: current_revision = current_revision.sum
        if not (current_revision == server_version[-1]['md5sum'] or\
                (current_revision is False and server_version[-1]['md5sum'] == base_version)):
            return (False, (_("Cannot continue while OpenERP Server version is different than database %s version! Try to login/logout again and restart OpenERP Server.") % cr.dbname))
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        try:
            res = proxy.get_next_revisions(self.get_uuid(cr, uid, context=context), self._hardware_id, current_revision)
        except osv.except_osv as e:
            if all(substr in e.value
                   for substr in
                   ('sync_manager', 'object has no attribute', 'get_next_revisions')):
                return (False, "The server doesn't seems to have the module update_server installed!")
            else:
                raise
        if res[0]:
            revisions._update(cr, uid, res[1].get('revisions', []), context=context)
            return ((res[1]['status'] != 'failed'), res[1]['message'])
        else:
            return res

entity()
