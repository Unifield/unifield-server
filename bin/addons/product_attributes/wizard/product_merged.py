# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _


class product_merged_wizard(osv.osv_memory):
    _name = 'product.merged.wizard'


    _columns = {
        'new_product_id': fields.many2one('product.product', 'UD NSL Product', readonly=1, required=1),
        'old_product_id': fields.many2one('product.product', 'Old local Product', select=1, domain=[('active', '=', True), ('international_status', '=', 'Local'), ('replaced_by_product_id', '=', False)]),
        'warning_msg': fields.text('Warning Message'),
        'warning_checked': fields.boolean('Warning Checked'),
    }


    def do_merge_product(self, cr, uid, ids, context=None):
        prod_obj = self.pool.get('product.product')
        wiz = self.browse(cr, uid, ids[0], context)

        block_msg = prod_obj.check_same_value(cr, uid, wiz.new_product_id.id, wiz.old_product_id.id, blocker=True, context=context)
        if block_msg:
            raise osv.except_osv(_('Warning'), block_msg)

        if not wiz.warning_checked:
            warn_msg = prod_obj.check_same_value(cr, uid, wiz.new_product_id.id, wiz.old_product_id.id, blocker=False, context=context)
            if warn_msg:
                self.write(cr, uid, ids, {'warning_msg': warn_msg, 'warning_checked': True}, context=context)
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.merged.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': ids[0],
                    'context': context,
                    'height': '300px',
                    'width': '720px',
                }


        prod_obj.merge_product(cr, uid, wiz.new_product_id.id, wiz.old_product_id.id, context=None)
        return {'type': 'ir.actions.act_window_close'}

    def change_warning(self, cr, uid, ids, context=None):
        return {'value': {'warning_checked': False, 'warning_msg': False}}

product_merged_wizard()
