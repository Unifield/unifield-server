# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _


class product_merged_wizard(osv.osv_memory):
    _name = 'product.merged.wizard'


    _columns = {
        'old_product_id': fields.many2one('product.product', 'Old local Product', readonly=1),
        'new_product_id': fields.many2one('product.product', 'UD Product'),
        'show_ud': fields.boolean('Use Standard / Non Standard UD product', help="Unticked: display UD NSL inactive products\nTicked: display UD ST + NS active products"),
        'ud_old_code': fields.char('UD Old code', readonly=1, size=1024),
        'warning_msg': fields.text('Warning Message'),
        'warning_checked': fields.boolean('Warning Checked'),
        'level': fields.char('Level', size=16),
    }

    def do_merge_product(self, cr, uid, ids, context=None):
        prod_obj = self.pool.get('product.product')
        wiz = self.browse(cr, uid, ids[0], context)


        if wiz.level == 'coordo':
            error_used = prod_obj._error_used_in_doc(cr, uid, wiz.new_product_id.id, context=context)
            if error_used:
                raise osv.except_osv(_('Warning'), _('The selected UD product has already been used in the past. Merge cannot be done for this product.'))

            has_pipe = prod_obj._has_pipe(cr, uid, wiz.new_product_id.id)
            if has_pipe:
                raise osv.except_osv(_('Warning'), _('Warning there is stock / pipeline in at least one of the instances in this mission! Therefore this product cannot be merged. Instances: %s') % (has_pipe[0][1], ))

        block_msg = prod_obj.check_same_value(cr, uid, wiz.new_product_id.id, wiz.old_product_id.id, level=wiz.level, blocker=True, context=context)
        if block_msg:
            raise osv.except_osv(_('Warning'), block_msg)

        if not wiz.warning_checked:
            warn_msg = []
            warn_value = prod_obj.check_same_value(cr, uid, wiz.new_product_id.id, wiz.old_product_id.id, level=wiz.level, blocker=False, context=context)
            if warn_value:
                warn_msg.append(warn_value)
            if wiz.level != 'coordo':
                warn_fields = []
                if not wiz.new_product_id.oc_subscription and wiz.old_product_id.oc_subscription:
                    warn_fields.append(_('OC Subscribed False'))
                if wiz.new_product_id.state_ud == 'archived' and wiz.new_product_id.state_ud != wiz.old_product_id.state_ud:
                    warn_fields.append(_('UD status Archived'))
                if warn_fields:
                    warn_msg.append(
                        _('Warning, the products you are about to merge do not have the same UD and OC Subscribed Statuses. Product %s which will be kept Active after this merge has %s, are you sure you wish to proceed with this merge?')
                        % (wiz.new_product_id.default_code, ', '.join(warn_fields))
                    )

            if warn_msg:
                self.write(cr, uid, ids, {'warning_msg': '\n'.join(warn_msg), 'warning_checked': True, 'ud_old_code': wiz.new_product_id.old_code}, context=context)
                view_id = False
                if wiz.level != 'coordo':
                    view_id = [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'hq_product_merged_wizard_form_view')[1]]
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.merged.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'view_id': view_id,
                    'res_id': ids[0],
                    'context': context,
                    'height': '400px',
                    'width': '720px',
                }


        if wiz.level == 'coordo':
            prod_obj.merge_product(cr, uid, wiz.new_product_id.id, wiz.old_product_id.id, context=None)
        else:
            prod_obj.merge_hq_product(cr, uid, wiz.new_product_id.id, wiz.old_product_id.id, context=None)

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'product.product_normal_action', ['form', 'tree'], context=context)
        res['res_id'] = wiz.new_product_id.id
        return res

    def do_hq_merge_product(self, cr, uid, ids, context=None):
        return self.do_merge_product(cr, uid, ids, context=context)

    def change_warning(self, cr, uid, ids, new_prod, context=None):
        old_code =False
        if new_prod:
            old_code = self.pool.get('product.product').browse(cr, uid, new_prod, fields_to_fetch=['old_code'], context=context).old_code
        return {'value': {'warning_checked': False, 'warning_msg': False, 'ud_old_code': old_code}}

product_merged_wizard()
