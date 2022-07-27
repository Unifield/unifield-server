# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.sql import drop_view_if_exists

class signature_follow_up(osv.osv):
    _name = 'signature.follow_up'
    _description = 'Signatures Follow-up'
    _rec_type = 'doc_name'
    _order = 'id desc'
    _auto = False

    def init(self, cr):
        drop_view_if_exists(cr, 'signature_follow_up')
        cr.execute("""
            create or replace view signature_follow_up as (
                select
                    user_rel.id as id,
                    user_rel.user_id as user_id,
                    s.signature_res_id as doc_id,
                    s.signature_state as status,
                    s.signature_res_model as doc_type,
                    count(l.user_id=user_rel.user_id or NULL) as signed,
                    coalesce(po.name, so.name) as doc_name,
                    min(case when l.user_id=user_rel.user_id then l.date else NULL end) as signature_date
                from
                    signature s
                inner join user_signature_rel user_rel on user_rel.signature_id = s.id
                inner join signature_line l on l.signature_id = s.id
                left join purchase_order po on po.id = s.signature_res_id and s.signature_res_model='purchase.order'
                left join sale_order so on so.id = s.signature_res_id and s.signature_res_model='sale.order'
                group by
                    user_rel.id, user_rel.user_id, s.signature_res_id, s.signature_state, s.signature_res_model, po.name, so.name
            )
        """)

    _columns = {
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'doc_name': fields.char('Document Name', size=256, readonly=1),
        'doc_type': fields.selection([('purchase.order', 'PO'), ('sale.order', 'IR')], 'Document Type', readonly=1),
        'doc_id': fields.integer('Doc ID', readonly=1),
        'status': fields.selection([('open', 'Open'), ('partial', 'Partially Signed'), ('signed', 'Fully Signed')], string='Signature State', readonly=1),
        'signed': fields.integer('Signed', readonly=1),
        'signature_date': fields.datetime('Signature Date', readonly=1),
    }

    def open_doc(self, cr, uid, ids, context=None):
        if not ids:
            return True
        doc = self.browse(cr, uid, ids[0], fields_to_fetch=['doc_type', 'doc_id'], context=context)
        action_xml_id = {
            'purchase.order': 'purchase.purchase_form_action',
            'sale.order': 'procurement_request.action_procurement_request',
        }
        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, action_xml_id[doc.doc_type], ['form', 'tree'],context=context)
        res['res_id'] = doc.doc_id
        res['target'] = 'current'
        res['keep_open'] = True
        return res

signature_follow_up()


