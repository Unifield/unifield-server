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
    
    _defaults = {
        'active' : False
    }
    
    def _get_last_revision(self, cr, uid, context=None):
        rev_ids = self.search(cr, uid, [('active', '=', True)], limit=1, context=context)
        if rev_ids:
            return rev_ids[0]
        return False
    
    
    
    
    _order = 'date desc'
    
version()
