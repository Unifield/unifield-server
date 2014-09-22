from osv import osv, orm

class res_log(osv.osv):

    _inherit = 'res.log'

    def create(self, cr, uid, vals, context=None):
        return super(res_log, self).create(cr, hasattr(uid, 'realUid') and uid.realUid or uid, vals, context=context)
    
res_log()
