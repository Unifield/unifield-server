'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
import tools
#import pprint
import sync_server
#pp = pprint.PrettyPrinter(indent=4)
import logging


class version(osv.osv):
    
    _name = "sync_server.version"
    
    _columns = {
        'name' : fields.char(string='Revision', size=256),
        'patch' : fields.binary('Patch'),
        'sum' : fields.char(string="Check Sum", size=256),
        'date' : fields.datetime(string="Revision Date"),
        'importance' : fields.selection([('required','Required'),('optional','Optional')], "Importance Flag"),
        'state' : fields.selection([('draft','Draft'),('confirmed','Confirmed')], string="State"),
    }
    
    _defaults = {
        'state' : 'draft',
    }

    _sql_constraints = [('unique_sum', 'unique(sum)', 'Patches must be unique!')]

    def _get_last_revision(self, cr, uid, context=None):
        rev_ids = self.search(cr, uid, [('state','=','confirmed')], limit=1, context=context)
        return rev_ids[0] if rev_ids else False
    
    def _get_next_revisions(self, cr, uid, current, context=None):
        if current:
            active = self.browse(cr, uid, current)
            revisions = self.search(cr, uid, [('date','>',active.date),('state','=','confirmed')], order='date asc')
        else:
            revisions = self.search(cr, uid, [('state','=','confirmed')], order='date asc')
        return revisions

    def _compare_with_last_rev(self, cr, uid, entity, rev_sum, context=None):
        # Search the client's revision when exists
        if rev_sum:
            rev_client = self.search(cr, uid, [('sum', '=', rev_sum), ('state', '=', 'confirmed')], limit=1, context=context)
            if not rev_client:
                return {'status' : 'failed',
                        'message' : 'Cannot find revision %s on the server' % (rev_sum)}
            rev_client = rev_client[0]

        # Otherwise, get the whole
        else:
            rev_client = None

        revisions = self._get_next_revisions(cr, uid, rev_client)

        if not revisions:
            return {'status' : 'ok', 
                    'message' : "Last revision"}
        
        # Save client revision in our database
        # TODO more accurate!
        self.pool.get("sync.server.entity")._set_version(cr, uid, entity.id, rev_client, context=context)
        revisions = self.read(cr, uid, revisions, ['name','sum','date','importance'], context=context)
        status = 'update'
        for rev in revisions:
            rev.pop('id')
            if rev['importance'] == 'required':
                status = 'failed'

        return {'status' : status,
                'message' : "There is %s update(s) available" % len(revisions),
                'revisions' : revisions}
        
    def _get_zip(self, cr, uid, sum, context=None):
        ids = self.search(cr, uid, [('sum','=',sum)], context=context)
        if not ids:
            return (False, "Cannot find sum %s!" % sum)
        rec = self.browse(cr, uid, ids, context=context)[0]
        if rec.state != 'confirmed':
            return (False, "The revision %s is not enabled!" % sum)
        return (True, rec.patch)

    def delete_revision(self, cr, uid, ids, context=None):
        return self.unlink(cr, uid, ids, context=context)
    
    def activate_revision(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'confirmed'}, context)

    _order = 'date desc'
    
version()



class entity(osv.osv):
    """ OpenERP entity name and unique identifier """
    _inherit = "sync.server.entity"

    _columns = {
        'version_id': fields.many2one('sync_server.version', 'Unifield Version', ondelete='set null', ),
    }
    
    def _set_version(self, cr, uid, ids, version_id, context=None):
        if version_id:
            return self.write(cr, uid, ids, {'version_id' : version_id}, context=context)
        else:
            return True
    
entity()



class sync_manager(osv.osv):
    _inherit = "sync.server.sync_manager"
    __logger = logging.getLogger('sync.server')
    
    @sync_server.sync_server.check_validated
    def get_next_revisions(self, cr, uid, entity, rev_sum, context=None):
        return (True, self.pool.get('sync_server.version')._compare_with_last_rev(cr, 1, entity, rev_sum))

    @sync_server.sync_server.check_validated
    def get_zip(self, cr, uid, entity, revision, context=None):
        return self.pool.get('sync_server.version')._get_zip(cr, 1, revision)
    
sync_manager()  

