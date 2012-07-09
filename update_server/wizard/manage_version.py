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
from datetime import datetime
from dateutil.relativedelta import relativedelta

class manage_version(osv.osv):
    
    _name = "sync_server.version.manager"
    
    _columns = {
        'name' : fields.char('Revision Tag', size=256),
        'hash' : fields.char('Commit Hash', size=512),
        'date' : fields.datetime('Revision Date', readonly=True),
        'version_ids' : fields.many2many('sync_server.version', 'sync_server_version_rel', 'wiz_id', 'version_id', string="History of revision", readonly=True, limit=10000),
        'create_date' : fields.datetime("Create date"),
               
    }
    
    def _get_version(self, cr, uid, context=None):
        return self.pool.get("sync_server.version").search(cr, uid, [], context=context)
    
    _defaults = {
        'date' : lambda *a : datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
        'version_ids' : _get_version
    }
    
    def add_revision(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            data = {
                'name' :  wiz.name,
                'commit' : wiz.hash,
                'date' : wiz.date,
            }
            res_id = self.pool.get("sync_server.version").create(cr, uid, data, context=context)
            self.write(cr, uid, [wiz.id], {'version_ids' : [(4, res_id)], 
                                           'name' : False, 
                                           'hash' : False, 
                                           'date' : datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, 
                       context=context)
        return True
            
            
    def vacuum(self, cr, uid):
        today = (datetime.now() + relativedelta(hours=-1)).strftime("%Y-%m-%d %H:%M:%S") 
        unlink_ids = self.search(cr, uid, [('create_date', '<', today)])
        print "auto Vacuum", unlink_ids
        self.unlink(cr, uid, unlink_ids)
        return True
    
    
manage_version()

