'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
from tools.translate import _
import tools
from tools import config
import os
from updater import *
import time
import logging

class version(osv.osv):
    
    _name = "sync_client.version"
    
    _columns = {
        'name' : fields.char(string='Tag', size=256, readonly=True),
        'patch' : fields.binary('Patch', readonly=True),
        'sum' : fields.char(string="Commit Hash", size=256, required=True, readonly=True),
        'date' : fields.datetime(string="Revision Date", readonly=True),
        'comment' : fields.text("Comment", readonly=True),
        'state' : fields.selection([('not-installed','Not Installed'),('need-restart','Need Restart'),('installed','Installed')], string="State", readonly=True),
        'applied' : fields.datetime("Applied", readonly=True),
        'importance' : fields.selection([('required','Required'),('optional','Optional')], "Importance Flag", readonly=True),
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
            for rev in set(server_version) - set([x['sum'] for x in current_versions]):
                versions_id[rev] = self.create(cr, 1, {'sum':rev, 'state':'installed', 'applied':now})
            # Update existing ones
            self.write(cr, 1, [x['id'] for x in current_versions \
                               if x['sum'] in server_version and not x['state'] == 'installed'], \
                              {'state':'installed','applied':now})
            # Set last revision (assure last update has the last applied date)
            time.sleep(1)
            self.write(cr, 1, [versions_id[server_version[-1]]], {'applied':fields.datetime.now()})
        except BaseException, e:
            self._logger.exception("version init failure!")

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
        rev_ids = self.search(cr, uid, [('state','=','installed')], limit=1, order='applied desc', context=context)
        return self.browse(cr, uid, rev_ids[0]) if rev_ids else False

    def _get_next_revisions(self, cr, uid, context=None):
        self.current = self._get_last_revision(cr, uid, context=context)
        return self.search(cr, uid, [('state','!=','installed')], order='date asc')

    def _is_outdated(self, cr, uid, context=None):
        if not hasattr(self, 'current'):
            self.current = self._get_last_revision(cr, uid, context=context) 
        if not hasattr(self, 'version_check'):
            where = [('state','!=','installed'),('importance','=','required')]
            if self.current:
                where.append(('date','>',self.current.date))
            self.version_check = self.search(cr, uid, where, limit=1)
        return bool(self.version_check)

    def _is_update_available(self, cr, uid, ids, context=None):
        for id in ids if isinstance(ids, list) else [ids]:
            if not self.browse(cr, uid, id, context=context).patch:
                return False
        return True

    _order = 'date desc'
    
version()

class entity(osv.osv):
    _inherit = "sync.client.entity"

    def get_upgrade_status(self, cr, uid, context=None):
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return _("OpenERP is restarting<br/>to finish upgrade...")
        if revisions._is_outdated(cr, uid, context=context):
            return _("Major upgrade is available.<br/>The synchronization process is disabled<br/>while the instance is not upgraded.")
        return ""

    def upgrade(self, cr, uid, context=None):
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return (False, "Need restart")
        current_revision = revisions._get_last_revision(cr, uid, context=context)
        if current_revision: current_revision = current_revision.sum
        if not (current_revision == server_version[-1] or (current_revision is False and server_version[-1] == base_version)):
            return (False, (_("Cannot continue while OpenERP Server version is different than database %s version! Try to login/logout again and restart OpenERP Server.") % cr.dbname))
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        try:
            res = proxy.get_next_revisions(self.get_uuid(cr, uid, context=context), current_revision)
        except osv.except_osv, e:
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
