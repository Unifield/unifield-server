#!/usr/bin/env python
# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
import decimal_precision as dp
from tools.translate import _


class esc_invoice_line(osv.osv):
    _name = 'esc.invoice.line'
    _description = 'International Invoices Line'
    _rec_name = 'po_name'
    _order = 'id desc'

    def _get_dest_instance_id(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        cur_instance = self.pool.get('res.company')._get_instance_record(cr, uid)
        if cur_instance.level != 'section':
            hq_id = cur_instance.parent_id.parent_id and cur_instance.parent_id.parent_id.id or cur_instance.parent_id.id or False
            for _id in ids:
                res[_id] = hq_id
            return res

        for esc_line in self.browse(cr, uid, ids, fields_to_fetch=['requestor_cc_id', 'consignee_cc_id'], context=context):
            cc = esc_line.consignee_cc_id or esc_line.requestor_cc_id
            res[esc_line.id] = cc.po_fo_cc_instance_ids and cc.po_fo_cc_instance_ids[0].id or False
        return res

    _columns = {
        'po_name': fields.char('PO Reference', size=64, required=1, select=1),
        'requestor_cc_id': fields.many2one('account.analytic.account', 'Requestor Cost Center', required=1, domain="[('category','=', 'OC'), ('type', '!=', 'view')]"),
        'consignee_cc_id': fields.many2one('account.analytic.account', 'Consignee Cost Center', domain="[('category','=', 'OC'), ('type', '!=', 'view')]"),
        'dest_instance_id': fields.function(_get_dest_instance_id, method=1, type='many2one', relation='msf.instance', string='Destination Instance'),
        'product_id': fields.many2one('product.product', 'Product', required=1, select=1),
        'price_unit': fields.float('Unit Price', required=1, digits_compute=dp.get_precision('Purchase Price Computation')),
        'product_qty': fields.float('Quantity', required=True, digits=(16, 2), related_uom='uom_id'),
        'remaining_qty': fields.float('Remaining Quantity', digits=(16, 2), readonly=1, related_uom='uom_id'),
        'uom_id': fields.many2one('product.uom', 'UoM'),
        'currency_id': fields.many2one('res.currency', 'Currency', required=1),
        'shipment_ref': fields.char('Field mapping with IN', size=128),

        'state': fields.selection([('1_draft', 'Draft'), ('0_open', 'Open'), ('done', 'Done')], 'State', readonly=1),

    }

    def _update_remaining(self, cr, uid, ids, vals, context=None):
        if not ids:
            return
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 'product_qty' in vals and vals.get('state', '1_draft') == '1_draft':
            cr.execute("update esc_invoice_line set remaining_qty=product_qty where state='1_draft' and id in %s", (tuple(ids), ))


    def write(self, cr, uid, ids, vals, context=None):
        ret = super(esc_invoice_line, self).write(cr, uid, ids, vals, context)
        self._update_remaining(cr, uid, ids, vals, context)
        return ret

    def create(self, cr, uid, vals, context=None):
        new_id = super(esc_invoice_line, self).create(cr, uid, vals, context)
        self._update_remaining(cr, uid, [new_id], vals, context)
        return new_id

    _defaults = {
        'state': '1_draft',
    }


    _sql_contraints = {
        ('product_qty', 'product_qty>0', 'Quantity must be greater than 0.'),
    }


esc_invoice_line()

class finance_price_track_changes(osv.osv):
    _name = 'finance_price.track_changes'
    _rec_name = 'product_id'
    _description = 'International Invoices Lines Matching'
    _order = 'id desc'

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True, readonly=True,  ondelete='cascade', select=1),
        'old_price': fields.float(string='Previous Finance Price', digits_compute=dp.get_precision('Purchase Price Computation'), required=False, readonly=True),
        'new_price': fields.float(string='New Finance Price', digits_compute=dp.get_precision('Purchase Price Computation'), required=False, readonly=True),
        'qty_processed': fields.float('Quantity Processed', readonly=True, digits=(16, 2)),
        'price_unit': fields.float('Unit Price', required=1, digits_compute=dp.get_precision('Purchase Price Computation'), readonly=True),
        'stock_before': fields.float('Qty in Stock Before', readonly=True, digits=(16, 2)),
        'matching_type': fields.selection([('iil', 'International Lines'), ('po', 'PO'), ('invoice', 'Invoice')], 'Matching Type', readonly=True),

        'stock_move_id': fields.many2one('stock.move', 'Move line', readonly=True),
        'stock_picking_id': fields.related('stock_move_id', 'picking_id', string='IN', type='many2one', relation='stock.picking', readonly=True, domain="[('type', '=', 'in'), ('state', '=', 'done')]"),

        'invoice_id': fields.many2one('account.invoice', 'Invoice', readonly=True),
        'invoice_line_id': fields.many2one('account.invoice.line', 'Invoice Line', readonly=True),

        'purchase_oder_line_id': fields.many2one('purchase.order.line', 'PO line', readonly=True),

        'esc_invoice_line_id': fields.many2one('esc.invoice.line', 'International Line', readonly=True),
    }

finance_price_track_changes()

class esc_line_setup(osv.osv_memory):
    _name = 'esc_line.setup'
    _inherit = 'res.config'

    _columns = {
        'esc_line': fields.boolean(string='Activate International Invoices Lines ?'),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        """
        if context is None:
            context = {}
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(esc_line_setup, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        res['esc_line'] = setup.esc_line
        return res

    def execute(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not isinstance(ids, list) or len(ids) != 1:
            raise osv.except_osv(_('Error'), _('An error has occurred with the item retrieved from the form. Please contact an administrator if the problem persists.'))
        wiz = self.browse(cr, uid, ids[0], fields_to_fetch=['esc_line'], context=context)
        setup_obj = self.pool.get('unifield.setup.configuration')
        setup = setup_obj.get_config(cr, uid)
        if setup:
            for module, xmlid in [('account_hq_entries', 'finance_price_track_changes_menu'), ('account_hq_entries', 'esc_invoice_line_menu'), ('account_hq_entries', 'esc_line_import_menu')]:
                menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, xmlid)[1]
                self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': wiz.esc_line}, context=context)
            setup_obj.write(cr, uid, [setup.id], {'esc_line': wiz.esc_line}, context=context)

esc_line_setup()
