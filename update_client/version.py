'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
import tools
from tools import config
import os
#import sync_server
#import pprint
#pp = pprint.PrettyPrinter(indent=4)
#import logging

update_directory = os.path.join(config['root_path'], ".update")
lock_file = os.path.join(config['root_path'], "update.lock")

class version(osv.osv):
    
    _name = "sync_client.version"
    
    _columns = {
        'name' : fields.char(string='Tag', size=256, required=True, readonly=True),
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
    
    _sql_constraints = [('unique_sum', 'unique(sum)', 'Patches must be unique!')]

    def _need_restart(self, cr, uid, context=None):
        return os.path.isfile(lock_file) #or bool(self.search(cr, uid, [('state','=','need-restart')], context=context))

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
        rev_ids = self.search(cr, uid, [('state','=','installed')], limit=1, context=context)
        return self.browse(cr, uid, rev_ids[0]) if rev_ids else False

    def _get_next_revisions(self, cr, uid, context=None):
        self.current = self._get_last_revision(cr, uid, context=context)
        if self.current:
            revisions = self.search(cr, uid, [('date','>',self.current.date),('state','!=','installed')], order='date asc')
        else:
            revisions = self.search(cr, uid, [('state','!=','installed')], order='date asc')
        return revisions

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
            return "OpenERP is restarting<br/>to finish upgrade..."
        if revisions._is_outdated(cr, uid, context=context):
            return "Major upgrade is available. The synchronization process<br />is disabled while the instance is not upgraded."
        return ""

    def upgrade(self, cr, uid, context=None):
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return (False, "Need restart")
        current_revision = revisions._get_last_revision(cr, uid, context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_next_revisions(self.get_uuid(cr, uid, context=context), current_revision.sum if current_revision else False)
        if res[0]:
            revisions._update(cr, uid, res[1].get('revisions', []), context=context)
            return ((res[1]['status'] != 'failed'), res[1]['message'])
        else:
            return res

entity()

