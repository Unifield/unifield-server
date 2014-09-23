from osv import osv, orm
from osv import fields

class res_log(osv.osv):

    _inherit = 'res.log'

    _columns = {
        'read_ok': fields.boolean(
            string='Read OK',
            help='Indicate if the user is able to open the document in res.log',
        ),
    }

    _defaults = {
        'read_ok': False,
    }

    def create(self, cr, uid, vals, context=None):
        if vals is None:
            vals = {}

        user_id = hasattr(uid, 'realUid') and uid.realUid or uid
        read_ok = False
        if user_id and vals.get('res_model', False):
            read_ok = self.pool.get('ir.model.access').check(cr, user_id, vals.get('res_model'), 'read', context=context)

        vals['read_ok'] = read_ok

        return super(res_log, self).create(cr, hasattr(uid, 'realUid') and uid.realUid or uid, vals, context=context)

    def get(self, cr, uid, context=None):
        unread_log_ids = self.search(cr, uid, [
            ('user_id', '=', uid),
            ('read', '=', False),
        ], context=context)

        list_of_fields = [
            'name',
            'res_model',
            'res_id',
            'context',
            'domain',
            'read_ok',
        ]

        res = self.read(cr, uid, unread_log_ids, list_of_fields, context=context)
        res.reverse()

        result = []
        res_dict = {}

        for r in res:
           t = (r['res_model'], r['res_id'])
           if t not in res_dict:
               res_dict[t] = True
               result.insert(0,r)
        
        self.write(cr, uid, unread_log_ids, {'read': True}, context=context)
        return result
    
res_log()
