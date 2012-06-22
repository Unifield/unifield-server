from osv import osv
from osv import fields

class ir_values(osv.osv):
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req)
        new_values = values
        
        accepted_values = {'client_action_multi': ['act_stock_return_picking'],
                           'client_print_multi': [],
                           'client_action_relate': ['View_log_stock.picking'],
                           'tree_but_action': [],
                           'tree_but_open': []}
        
        if context.get('picking_type', False) == 'incoming_shipment' and 'stock.picking' in [x[0] for x in models]:
            new_values = []
            for v in values:
                if key == 'action' and v[1] in accepted_values[key2]:
                    new_values.append(v)
 
        return new_values

ir_values()