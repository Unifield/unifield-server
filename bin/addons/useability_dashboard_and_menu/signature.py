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
                    case
                        when jour.type is not null then s.signature_res_model||'.'||jour.type
                        when invoice.real_doc_type = 'donation' or invoice.type='in_invoice' and not coalesce(invoice.is_debit_note, 'f') and coalesce(invoice.is_inkind_donation, 'f') then 'account.invoice.donation'
                        when invoice.real_doc_type = 'si' or invoice.type='in_invoice' and not coalesce(invoice.is_debit_note, 'f') and not coalesce(invoice.is_inkind_donation, 'f') and not coalesce(invoice.is_direct_invoice, 'f')  and not coalesce(invoice.is_intermission, 'f') then 'account.invoice.si'
                        else s.signature_res_model end as doc_type,
                    l.subtype as subtype,
                    count(l.user_id=user_rel.user_id or NULL) as signed,
                    coalesce(po.name, so.name, invoice.number, invoice.name, pick.name, jour.code|| ' ' ||per.name) as doc_name,
                    min(case when l.user_id=user_rel.user_id then l.date else NULL end) as signature_date
                from
                    signature s
                inner join signature_users_allowed user_rel on user_rel.signature_id = s.id
                inner join signature_line l on l.signature_id = s.id and l.subtype=user_rel.subtype
                left join purchase_order po on po.id = s.signature_res_id and s.signature_res_model='purchase.order'
                left join sale_order so on so.id = s.signature_res_id and s.signature_res_model='sale.order'
                left join account_invoice invoice on invoice.id = s.signature_res_id and s.signature_res_model='account.invoice'

                left join account_bank_statement st on st.id = s.signature_res_id and s.signature_res_model='account.bank.statement'
                left join account_period per on per.id = st.period_id
                left join account_journal jour on jour.id = st.journal_id

                left join stock_picking pick on pick.id =  s.signature_res_id and s.signature_res_model='stock.picking'
                group by
                    user_rel.id, user_rel.user_id, s.signature_res_id, s.signature_state, s.signature_res_model, po.name, so.name, jour.code, jour.type, per.name, l.subtype, pick.name,
                    invoice.real_doc_type, invoice.type, invoice.is_debit_note, invoice.is_inkind_donation, invoice.is_direct_invoice, invoice.is_intermission, invoice.number, invoice.name
            )
        """)

    _columns = {
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'doc_name': fields.char('Document Name', size=256, readonly=1),
        'doc_type': fields.selection([
            ('purchase.order', 'PO'), ('sale.order', 'IR'),
            ('account.bank.statement.cash', 'Cash Register'), ('account.bank.statement.bank', 'Bank Register'),
            ('account.invoice.si', 'Supplier Invoice'), ('account.invoice.donation', 'Donation'),
            ('stock.picking', 'IN'),
        ], 'Document Type', readonly=1),
        'doc_id': fields.integer('Doc ID', readonly=1),
        'status': fields.selection([('open', 'Open'), ('partial', 'Partially Signed'), ('signed', 'Fully Signed')], string='Signature State', readonly=1),
        'signed': fields.integer('Signed', readonly=1),
        'signature_date': fields.datetime('Signature Date', readonly=1),
        'subtype': fields.selection([('full', 'Full Report'), ('rec', 'Reconciliation')], string='Type of signature', readonly=1),
    }

    def open_doc(self, cr, uid, ids, context=None):
        if not ids:
            return True
        doc = self.browse(cr, uid, ids[0], fields_to_fetch=['doc_type', 'doc_id'], context=context)
        action_xml_id = {
            'purchase.order': 'purchase.purchase_form_action',
            'sale.order': 'procurement_request.action_procurement_request',
            'account.invoice.si': 'account.action_invoice_tree2',
            'account.invoice.donation': 'account_override.action_inkind_donation',
            'stock.picking': 'stock.action_picking_tree4',
        }
        if doc.doc_type.startswith('account.bank.statement'):
            register_type = doc.doc_type.split('.')[-1]
            res = self.pool.get('account.bank.statement').get_statement(cr, uid, ids[0], register_type, context=context)
            res['views'] = [res['views'][1], res['views'][0]]
        else:
            res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, action_xml_id[doc.doc_type], ['form', 'tree'],context=context)

        res['res_id'] = doc.doc_id
        res['target'] = 'current'
        res['keep_open'] = True
        return res

signature_follow_up()


