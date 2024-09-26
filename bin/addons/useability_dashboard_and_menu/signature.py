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
                    min(l.id) as id,
                    l.user_id as user_id,
                    s.signature_res_id as doc_id,
                    s.signature_state as status,
                    case
                        when jour.type is not null then s.signature_res_model||'.'||jour.type
                        when invoice.real_doc_type = 'donation' or invoice.type='in_invoice' and not coalesce(invoice.is_debit_note, 'f') and coalesce(invoice.is_inkind_donation, 'f') then 'account.invoice.donation'
                        when invoice.real_doc_type = 'si' or invoice.type='in_invoice' and not coalesce(invoice.is_debit_note, 'f') and not coalesce(invoice.is_inkind_donation, 'f') and not coalesce(invoice.is_direct_invoice, 'f')  and not coalesce(invoice.is_intermission, 'f') then 'account.invoice.si'
                        when so.procurement_request = 't' then 'sale.order.ir'
                        when so.procurement_request = 'f' then 'sale.order.fo'
                        when pick.type = 'in' and pick.subtype = 'standard' then 'stock.picking.in'
                        when pick.type = 'out' and pick.subtype = 'standard' then 'stock.picking.out'
                        when pick.type = 'out' and pick.subtype = 'picking' then 'stock.picking.pick'
                        else s.signature_res_model end as doc_type,
                    string_agg(distinct(l.name), ',') as roles,
                    bool_and(l.signed) as signed,
                    coalesce(po.name, so.name, invoice.number, invoice.name, pick.name, jour.code|| ' ' ||per.name) as doc_name,
                    min(case when l.signed then l.date else NULL end) as signature_date,
                    coalesce(po.state, so.state, invoice.state, st.state, pick.state) as doc_state,
                    s.signature_is_closed as signature_is_closed,
                    coalesce(min(priol.prio) < min(l.prio), 'f') as wait_prio,
                    case
                        when s.signature_res_model in ('sale.order', 'purchase.order') and
                            (
                                so.state not in ('draft', 'draft_p', 'validated', 'validated_p')
                                    or po.state not in ('draft', 'draft_p', 'validated', 'validated_p')
                            ) then False
                        else True end as allowed_to_be_signed
                from
                    signature s
                inner join signature_line l on l.signature_id = s.id
                left join signature_line priol on priol.signature_id = l.signature_id and priol.prio < l.prio and priol.signed='f' and priol.is_active='t' and priol.user_id != l.user_id
                left join purchase_order po on po.id = s.signature_res_id and s.signature_res_model='purchase.order'
                left join sale_order so on so.id = s.signature_res_id and s.signature_res_model='sale.order'
                left join account_invoice invoice on invoice.id = s.signature_res_id and s.signature_res_model='account.invoice'

                left join account_bank_statement st on st.id = s.signature_res_id and s.signature_res_model='account.bank.statement'
                left join account_period per on per.id = st.period_id
                left join account_journal jour on jour.id = st.journal_id

                left join stock_picking pick on pick.id =  s.signature_res_id and s.signature_res_model='stock.picking'
                where
                    l.user_id is not null and s.signed_off_line = 'f'
                group by
                    l.user_id, s.signature_res_id, s.signature_state, s.signature_res_model, s.signature_is_closed, po.name, so.name, jour.code, jour.type, per.name, pick.name,
                    invoice.real_doc_type, invoice.type, invoice.is_debit_note, invoice.is_inkind_donation, invoice.is_direct_invoice, invoice.is_intermission, invoice.number, invoice.name,
                    po.state, so.state, so.procurement_request, invoice.state, st.name, pick.state, pick.type, pick.subtype, st.state
            )
        """)


    def _get_all_states(self, cr, uid, context=None):
        st = {}
        for obj in ['purchase.order', 'sale.order', 'stock.picking', 'account.bank.statement', 'account.invoice']:
            st.update(dict(self.pool.get(obj)._columns['state'].selection))
        return list(st.items())

    _columns = {
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'doc_name': fields.char('Document Name', size=256, readonly=1),
        'doc_type': fields.selection([
            ('purchase.order', 'PO'), ('sale.order.fo', 'FO'), ('sale.order.ir', 'IR'),
            ('account.bank.statement.cash', 'Cash Register'), ('account.bank.statement.bank', 'Bank Register'), ('account.bank.statement.cheque', 'Cheque Register'),
            ('account.invoice.si', 'Supplier Invoice'), ('account.invoice.donation', 'Donation'),
            ('stock.picking.in', 'IN'), ('stock.picking.out', 'OUT'), ('stock.picking.pick', 'Pick'),
        ], 'Document Type', readonly=1),
        'doc_id': fields.integer('Doc ID', readonly=1),
        'status': fields.selection([('open', 'Open'), ('partial', 'Partially Signed'), ('signed', 'Fully Signed')], string='Signature State', readonly=1),
        'doc_state': fields.selection(_get_all_states, string='Document State', readonly=1),
        'signed': fields.boolean('Signed', readonly=1),
        'signature_date': fields.datetime('Signature Date', readonly=1),
        'roles': fields.char('Roles', size=256, readonly=1),
        'signature_is_closed': fields.boolean('Signature Closed', readonly=1),
        'wait_prio': fields.boolean('Has signature before this one.'),
        'allowed_to_be_signed': fields.boolean('Allowed to be signed', readonly=1),
    }

    def open_doc(self, cr, uid, ids, context=None):
        if not ids:
            return True
        doc = self.browse(cr, uid, ids[0], fields_to_fetch=['doc_type', 'doc_id', 'doc_name'], context=context)
        action_xml_id = {
            'purchase.order': 'purchase.purchase_form_action',
            'sale.order.fo': 'sale.action_order_form',
            'sale.order.ir': 'procurement_request.action_procurement_request',
            'account.invoice.si': 'account.action_invoice_tree2',
            'account.invoice.donation': 'account_override.action_inkind_donation',
            'stock.picking.in': 'stock.action_picking_tree4',
            'stock.picking.out': 'stock.action_picking_tree',
            'stock.picking.pick': 'msf_outgoing.action_picking_ticket',
        }
        if doc.doc_type.startswith('account.bank.statement'):
            register_type = doc.doc_type.split('.')[-1]
            res = self.pool.get('account.bank.statement').get_statement(cr, uid, ids[0], register_type, context=context)
            res['views'] = [res['views'][1], res['views'][0]]
        else:
            res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, action_xml_id[doc.doc_type], ['form', 'tree'],context=context)

        res.update({
            'name': doc.doc_name,
            'res_id': doc.doc_id,
            'target': 'current',
            'keep_open': True,
            'domain': [('id', '=', doc.doc_id)]
        })
        return res


signature_follow_up()
