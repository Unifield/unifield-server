from osv import osv, orm

class res_log(osv.osv):

    _inherit = 'res.log'

    def create(self, cr, uid, vals, context=None):
        if hasattr(uid, 'realUid'):
            return super(res_log, self).create(cr, uid.realUid, vals, context=context)
        return super(res_log, self).create(cr, uid, vals, context=context)
res_log()