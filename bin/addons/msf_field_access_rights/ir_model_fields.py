from osv import osv, orm, fields

class ir_model_field(osv.osv):
    _inherit = 'ir.model.fields'

    _columns = {
        'uom_id': fields.many2one('product.uom', 'UoM'),
    }
    
    def _modify_search_args(self, args):
        if hasattr(args, '__iter__'):
            for index, arg in enumerate(args):
                if isinstance(arg, (list, tuple)) and arg[0] == 'model_id' and arg[1] == 'in' and isinstance(arg[2], (list, tuple)) and isinstance(arg[2][0], tuple) and len(arg[2][0]) == 3 and arg[2][0][0] == 6:
                    args[index] = ('model_id', 'in', arg[2][0][2])
        return args
   
    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        args = self._modify_search_args(args)
        return super(ir_model_field, self).name_search(cr, uid, name, args=args, operator=operator, context=context, limit=limit)
        
    def search(self, cr, uid, args, offset=0, limit=None, order='', context=None, count=False):
        args = self._modify_search_args(args)
        return super(ir_model_field, self).search(cr, uid, args, offset, limit,
                order, context, count)
ir_model_field()
