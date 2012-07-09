'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
import tools
import pprint
import sync_server
pp = pprint.PrettyPrinter(indent=4)
import logging


class version(osv.osv):
    
    _name = "sync_client.version"
    
    _columns = {
        'name' : fields.char(string='Tag', size=256),
        'commit' : fields.char(string="Commit Hash", size=256),
        'date' : fields.datetime(string="Revision Date"),
        'active' : fields.boolean("Active"),
    }
    
    def _get_last_revision(self, cr, uid, context=None):
        rev_ids = self.search(cr, uid, [('active', '=', True)], limit=1, context=context)
        if rev_ids:
            return rev_ids[0]
        return False
    
    def _save_rev(self, cr, uid, entity, rev_id, context=None):
        self.pool.get()
    
    def _compare_with_last_rev(self, cr, uid, entity, rev_tag, rev_hash, rev_date, context=None):
        rev_id_client = self.search(cr, uid, [('name', '=', rev_tag), ('commit', '=', rev_hash), ('date', '=', rev_date)], context=context)
        last_rev_id = self._get_last_revision(cr, uid, context)
        if not last_rev_id:
            return True
        
        if not rev_id_client:
            return ('The revision send [%s %s - %s ] does not match with any revision on the server' % (rev_tag, rev_hash, rev_date))
        
        #save rev information
        self.pool.get("sync.server.entity")._set_version(cr, uid, entity.id, rev_id_client, context=context)
        
        if rev_id_client == last_rev_id:
            return True
        else:
            revision = self.browse(cr, uid, last_rev_id, context=context)
            return ("Need to be updated", revision.name, revision.commit, revision.date)
        
    def delete_revision(self, cr, uid, ids, context=None):
        self.unlink(cr, uid, ids, context=context)
        return True
    
    _order = 'date desc'
    
version()
