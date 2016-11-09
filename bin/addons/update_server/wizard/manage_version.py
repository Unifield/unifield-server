'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
import tools
#import pprint
#import sync_server
#pp = pprint.PrettyPrinter(indent=4)
#import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
import hashlib
from base64 import b64decode
import mimetypes
#from zipfile import is_zipfile
#from StringIO import StringIO

mimetypes.init()

class manage_version(osv.osv):
    
    _name = "sync_server.version.manager"
    
    _columns = {
        'name' : fields.char('Revision', size=256),
        'patch' : fields.binary('Patch'),
        'date' : fields.datetime('Date', readonly=True),
        'comment' : fields.text("Comment"),
        'version_ids' : fields.many2many('sync_server.version', 'sync_server_version_rel', 'wiz_id', 'version_id', string="History of Revision", readonly=True, limit=10000),
        'create_date' : fields.datetime("Create Date"),
        'importance' : fields.selection([('required','Required'),('optional','Optional')], "Importance Flag"),
        'state' : fields.selection([('upload','Upload'), ('error', 'Error')], "State"),
        'message' : fields.text("Message"),
    }
    
    def _get_version(self, cr, uid, context=None):
        return self.pool.get("sync_server.version").search(cr, uid, [], context=context)
    
    _defaults = {
        'date' : fields.datetime.now,
        'version_ids' : _get_version,
        'state' : 'upload',
    }
    
    def back(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {
            'state' : 'upload',
            'message' : '',
            'patch' : False,
        }, context=context)

    def add_revision(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if not wiz.patch:
                return self.write(cr, uid, ids, {
                    'state' : 'error',
                    'message' : "Missing patch file.",
                }, context=context)
            patch = b64decode(wiz.patch)
            #TODO import zipfile from python 2.7
            #fh_patch = StringIO(patch)
            #if not is_zipfile(fh_patch):
            if not patch[:2] == 'PK':
                return self.write(cr, uid, ids, {
                    'state' : 'error',
                    'message' : "The patch you tried to upload doesn't looks like a ZIP file! Please upload only zip files.",
                }, context=context)
            m = hashlib.md5(patch)
            data = {
                'name' :  wiz.name,
                'sum' : m.hexdigest(),
                'date' : fields.datetime.now(),
                'patch' : wiz.patch,
                'comment' : wiz.comment,
                'importance' : wiz.importance,
            }
            res_id = self.pool.get("sync_server.version").create(cr, uid, data, context=context)
            self.write(cr, uid, [wiz.id], {'version_ids' : [(4, res_id)], 
                                           'name' : False, 
                                           'patch' : False,
                                           'importance' : False,
                                           'date' : fields.datetime.now(), 
                                           'comment' : False},
                       context=context)
        return True
            
            
    def vacuum(self, cr, uid):
        now = (datetime.now() + relativedelta(hours=-1)).strftime("%Y-%m-%d %H:%M:%S") 
        unlink_ids = self.search(cr, uid, [('create_date', '<', now)])
        if unlink_ids:
            self.unlink(cr, uid, unlink_ids)
        return True
    
    
manage_version()

