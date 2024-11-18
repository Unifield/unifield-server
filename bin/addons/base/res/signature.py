# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.translate import _
from tools import ustr
from tools.misc import fakeUid
from tools.misc import escape_html
from tools.misc import _register_log
from lxml import etree
from datetime import datetime
from datetime import timedelta

from report.render.rml2pdf import customfonts
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO

list_sign = {
    'purchase.order': [
        # (key, label, active, prio)
        ('sr', _('Supply Responsible'), True, 1),
        ('tr', _('Technical Responsible'), True, 2),
        ('fr', _('Finance Responsible'), True, 3),
        ('mr', _('Mission Responsible'), False, 4),
        ('hq', _('HQ'), False, 5),
    ],
    'sale.order.fo': [
        ('sr', _('Supply Responsible'), True, 1),
        ('tr', _('Technical Responsible'), True, 2),
        ('fr', _('Finance Responsible'), True, 3),
        ('mr', _('Mission Responsible'), False, 4),
        ('hq', _('HQ'), False, 5),
    ],
    'sale.order.ir': [
        ('tr', _('Technical Responsible'), True, 1),
        ('sr', _('Supply Responsible'), True, 2),
    ],
    'account.bank.statement.cash': [
        ('fr', _('Signature 1 - reconciliation'), True, 1),
        ('mr', _('Signature 2 - reconciliation'), True, 1),
        ('fr_report', _('Signature 1 - full report'), True, 1),
        ('mr_report', _('Signature 2 - full report'), True, 1),
    ],
    'account.bank.statement.bank': [
        ('fr', _('Signature 1 - reconciliation'), True, 1),
        ('mr', _('Signature 2 - reconciliation'), True, 1),
        ('fr_report', _('Signature 1 - full report'), True, 1),
        ('mr_report', _('Signature 2 - full report'), True, 1),
    ],
    'account.bank.statement.cheque': [
        ('fr_report', _('Signature 1 - full report'), True, 1),
        ('mr_report', _('Signature 2 - full report'), True, 1),
    ],
    'account.invoice': [
        ('sr', _('Supply Responsible'), True, 1),
        ('tr', _('Technical Responsible'), True, 1),
        ('fr', _('Finance Responsible'), True, 1),
        ('mr', _('Mission Responsible'), False, 1),
    ],
    'stock.picking.in': [
        ('tr', _('Receiver'), True, 1),
        ('sr', _('Controller'), True, 2),
    ],
    'stock.picking.out': [
        ('sr', _('Approved by'), True, 1),
        ('tr', _('Logistic / Supply'), True, 1),
        ('fr', _('Storekeeper'), True, 1),
        ('mr', _('Receiver'), True, 1),
    ],
    'stock.picking.pick': [
        ('sr', _('Approved by'), True, 1),
        ('tr', _('Picked by'), True, 1),
        ('fr', _('Validated by'), True, 1),
    ],
    'physical.inventory': [
        ('wr', _('Warehouse Responsible'), True, 1),
        ('sr', _('Supply Responsible'), True, 1),
        ('so', _('Stock Owner'), True, 1),
    ],
}

saved_name = {
    'purchase.order': lambda doc: doc.name,
    'sale.order': lambda doc: doc.name,
    'account.bank.statement': lambda doc: '%s %s' %(doc.journal_id.code, doc.period_id.name),
    'account.invoice': lambda doc: doc.name or doc.number,
    'stock.picking': lambda doc: doc.name,
    'physical.inventory': lambda doc: doc.ref,
}
saved_value = {
    'purchase.order': lambda doc: round(doc.amount_total, 2),
    'sale.order': lambda doc: doc.procurement_request and round(doc.ir_total_amount, 2) or round(doc.functional_amount_total, 2),
    'account.bank.statement': lambda doc: doc.journal_id.type in ('bank', 'cheque') and round(doc.balance_end, 2) or doc.journal_id.type == 'cash' and round(doc.msf_calculated_balance, 2) or 0,
    'account.invoice': lambda doc: round(doc.amount_total, 2),
    'stock.picking': lambda doc: False,
    'physical.inventory': lambda doc: doc.discrepancy_lines_value,
}

saved_unit = {
    'purchase.order': lambda doc: doc.currency_id.name,
    'sale.order': lambda doc: doc.functional_currency_id.name,
    'account.bank.statement': lambda doc: doc.currency.name,
    'account.invoice': lambda doc: doc.currency_id.name,
    'stock.picking': lambda doc: doc.type == 'out' and doc.subtype == 'picking' and doc.total_qty_process_str or doc.total_qty_str,
    'physical.inventory': lambda doc: doc.company_id.currency_id.name,
}

saved_state = {
    'purchase.order': lambda doc: doc.state,
    'sale.order': lambda doc: doc.state,
    'account.bank.statement': lambda doc: doc.state,
    'account.invoice': lambda doc: doc.state,
    'stock.picking': lambda doc: doc.state,
    'physical.inventory': lambda doc: doc.state,
}



class signature(osv.osv):
    _name = 'signature'
    _rec_name = 'signature_state'
    _description = 'Signature options on documents'
    _record_source = True

    def _get_signature_available(self, cr, uid, ids, *a, **b):
        ret = {}
        available = self.pool.get('unifield.setup.configuration').get_config(cr, uid, 'signature')
        for _id in ids:
            ret[_id] = available
        return ret

    def _get_allowed_to_be_signed_unsigned(self, cr, uid, ids, *a, **b):
        '''
        Check if signature and un-signature is permitted on the document.
        For FO/IR/PO, only draft and validated documents. No restrictions on others
        '''
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for sign in self.read(cr, uid, ids, ['signature_res_model', 'signature_res_id']):
            allow = True
            model_obj = self.pool.get(sign['signature_res_model'])
            if sign['signature_res_model'] in ('sale.order', 'purchase.order') and sign['signature_res_id'] and \
                    model_obj.read(cr, uid, sign['signature_res_id'], ['state'])['state'] not in ('draft', 'draft_p', 'validated', 'validated_p'):
                allow = False
            res[sign['id']] = allow
        return res

    def _get_allowed_to_be_locked(self, cr, uid, ids, *a, **b):
        '''
        Check if locking the signature is allowed
        For PO, supplier must be external. Not allowed otherwise
        '''
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for sign in self.read(cr, uid, ids, ['signature_res_model', 'signature_res_id']):
            allow = False
            model_obj = self.pool.get(sign['signature_res_model'])
            if sign['signature_res_model'] == 'purchase.order' and sign['signature_res_id'] and \
                    model_obj.read(cr, uid, sign['signature_res_id'], ['partner_type'])['partner_type'] == 'external':
                allow = True
            res[sign['id']] = allow
        return res

    _columns = {
        'signature_line_ids': fields.one2many('signature.line', 'signature_id', 'Lines'),
        'signature_res_model': fields.char('Model', size=254, select=1),
        'signature_res_id': fields.integer('Id', select=1),
        'signature_state': fields.selection([('open', 'Open'), ('partial', 'Partially Signed'), ('signed', 'Fully Signed')], string='Signature State', readonly=True),
        'signed_off_line': fields.boolean('Signed Off Line'),
        'signature_is_closed': fields.boolean('Signature Closed', readonly=True),
        'signature_available': fields.function(_get_signature_available, type='boolean', string='Signature Available', method=1),
        'signature_closed_date': fields.datetime('Date of signature closure', readonly=1),
        'signature_closed_user': fields.many2one('res.users', 'Closed by', readonly=1),
        'allowed_to_be_signed_unsigned': fields.function(_get_allowed_to_be_signed_unsigned, type='boolean', string='Allowed to be signed/un-signed', method=1),
        'allowed_to_be_locked': fields.function(_get_allowed_to_be_locked, type='boolean', string='Allowed to be locked', method=1),
        'doc_locked_for_sign': fields.boolean('Document is locked because of signature', readonly=True),
    }

    _defaults = {
        'doc_locked_for_sign': False,
    }

    _sql_constraints = [
        ('unique_signature_res_id_model,', 'unique(signature_res_id, signature_res_model)', 'Signature must be unique'),
    ]

    def _log_sign_state(self, cr, uid, _id, model, old, new, context=None):
        if old != new:
            states_dict = dict(self._columns['signature_state'].selection)
            _register_log(self, cr, uid, _id, model, 'Signature State', states_dict.get(old, old) or '', states_dict.get(new, new) or '', 'write', context)

    def _set_signature_state(self, cr, uid, ids, context=None):
        assert len(ids) < 2, '_set_signature_state: only 1 id is allowed'

        sig_line_obj = self.pool.get('signature.line')
        nb_sign = sig_line_obj.search(cr, uid, [
            ('signature_id', '=', ids[0]),
            ('signed', '=', True),
            ('is_active', '=', True)
        ], count=True, context=context)
        if not nb_sign:
            signature_state = 'open'
        else:
            nb_unsign = sig_line_obj.search(cr, uid, [
                ('signature_id', '=', ids[0]),
                ('signed', '=', False),
                ('is_active', '=', True)
            ], count=True, context=context)
            if not nb_unsign:
                signature_state = 'signed'
            else:
                signature_state = 'partial'

        cur_obj = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_state', 'signature_res_id', 'signature_res_model'], context=context)
        if cur_obj.signature_state != signature_state:
            self.write(cr, uid, ids, {'signature_state': signature_state}, context=context)
            self._log_sign_state(cr, uid, cur_obj.signature_res_id, cur_obj.signature_res_model, cur_obj.signature_state, signature_state, context)
        return signature_state

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if not context:
            context = {}

        # To prevent unwanted locking when the lock button is available before other data has been saved in the document
        if 'doc_locked_for_sign' in vals and vals.get('doc_locked_for_sign', False):
            for sign in self.read(cr, uid, ids, ['allowed_to_be_locked'], context=context):
                if not sign['allowed_to_be_locked']:
                    raise osv.except_osv(_('Warning'), _("You are not allowed to lock this document, please refresh the page"))

        return super(signature, self).write(cr, uid, ids, vals, context=context)


signature()


class signature_object(osv.osv):
    """
        this object must be inherited on document to allow signature
           i.e: _inherit = 'signature.object'

        database column signature_id is added to the document's _table

        fields of signature.object can be browsed from the document
        all methods of this object are available from the document
            ("self" is the document itself)
    """

    _name = 'signature.object'
    _description = 'Abstract object to enable signature on document'

    _inherits = {'signature': 'signature_id'}

    # do not create table signature_object
    _auto = False

    def _get_locked_by_signature(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}

        res = {}
        for obj in self.browse(cr, uid, ids, fields_to_fetch=['signature_id'], context=context):
            res[obj.id] = obj.signature_id.doc_locked_for_sign

        return res

    _columns = {
        'signature_id': fields.many2one('signature', 'Signature', required=True, ondelete='cascade'),
        'locked_by_signature': fields.function(_get_locked_by_signature, type='boolean', string='Locked by signature',
                                               method=True, readonly=True, help='To prevent edition on: PO', store=False),
    }

    def action_close_signature(self, cr, uid, ids, context=None):
        _register_log(self, cr, uid, ids, self._name, 'Close Signature', False, True, 'write', context)
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.write(cr, uid, ids, {
            'signature_is_closed': True,
            'signature_closed_date': fields.datetime.now(),
            'signature_closed_user': real_uid,
        }, context=context)
        return True

    def sig_line_change(self, cr, uid, ids, context=None):
        states = dict(self._inherit_fields['signature_state'][2].selection)
        translated_states = dict([(k, _(v)) for k, v in list(states.items())])

        doc = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_state'], context=context)
        return {'value': {'signature_state': doc.signature_state}, 'display_strings': {'signature_state': translated_states}}

    def add_user_signatures(self, cr, uid, ids, context=None):
        doc_name = self.name_get(cr, uid, ids, context=context)[0][1]

        ftf = ['signature_id', 'signature_res_model', 'signature_line_ids']
        if self._name == 'account.bank.statement':
            ftf += ['journal_id']
        if self._name == 'purchase.order':
            ftf += ['partner_type', 'order_line', 'analytic_distribution_id']
        doc = self.browse(cr, uid, ids[0], fields_to_fetch=ftf, context=context)

        # Checks on specific document types to see if signatures can be added
        errors_msg = []
        if self._name == 'purchase.order' and doc.partner_type == 'external':
            if not doc.order_line:
                errors_msg.append(_('there are no lines'))
            else:
                if not doc.analytic_distribution_id:
                    cr.execute("""SELECT line_number FROM purchase_order_line 
                        WHERE order_id = %s AND analytic_distribution_id IS NULL ORDER BY line_number""", (doc.id,))
                    lines_no_ad = ', '.join([str(x[0]) for x in cr.fetchall()])
                    if lines_no_ad:
                        errors_msg.append(_('the line number(s) %s have no AD') % (lines_no_ad,))
                cr.execute("""SELECT line_number FROM purchase_order_line 
                    WHERE order_id = %s AND price_unit = 0 ORDER BY line_number""", (doc.id,))
                lines_no_price = ', '.join([str(x[0]) for x in cr.fetchall()])
                if lines_no_price:
                    errors_msg.append(_('the line number(s) %s have a unit price of 0') % (lines_no_price,))

            if errors_msg:
                raise osv.except_osv(_('Warning'), _('Document can not be signed as %s') % ('; '.join(errors_msg),))

        wiz_data = {
            'name': doc_name,
            'signature_id': doc.signature_id.id,
            'doc_locked_for_sign': doc.signature_id.doc_locked_for_sign,
        }
        view_id = [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'signature_add_user_wizard_form')[1]]
        x = 0
        for line in doc.signature_line_ids:
            wiz_data.update({
                'line_id_%d' % x : line.id,
                'role_%d' % x : line.name,
                'active_%d' % x: line.is_active,
                'backup_%d' % x: line.backup,
                'legal_name_%d' % x: line.user_id and line.user_id.esignature_id and line.user_id.esignature_id.legal_name or '',
                'login_%d' % x: line.user_id and line.user_id.id or False,
                'username_%d' % x: line.user_id and line.user_id.login or False,
                'signed_%d' % x: line.signed,
            })
            x += 1

        wiz_id = self.pool.get('signature.add_user.wizard').create(cr, uid, wiz_data, context=context)
        context['wiz_id'] = wiz_id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'signature.add_user.wizard',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'view_id': view_id,
            'height': '400px',
            'width': '920px',
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if not context:
            context = {}
        fvg = super(signature_object, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            signature_enable = self.pool.get('unifield.setup.configuration').get_config(cr, uid, 'signature')
            if not signature_enable or self._name == 'account.invoice' and context.get('doc_type') not in ('si', 'donation'):
                arch = etree.fromstring(fvg['arch'])
                fields = arch.xpath('//page[@name="signature_tab"]')
                if fields:
                    for to_remove in ['signature_state', 'signed_off_line', 'signature_line_ids', 'signature_is_closed']:
                        if fvg.get('fields') and to_remove in fvg['fields']:
                            del fvg['fields'][to_remove]
                    parent_node = fields[0].getparent()
                    parent_node.remove(fields[0])
                    fvg['arch'] = etree.tostring(arch, encoding='unicode')
            elif self._name == 'account.bank.statement':
                arch = etree.fromstring(fvg['arch'])
                fields = arch.xpath('//page[@name="signature_tab"]')
                if fields:
                    fields[0].attrib['attrs'] = "{'invisible': [('local_register', '=', False)]}"
                    fvg['arch'] = etree.tostring(arch, encoding='unicode')

        return fvg

    def activate_offline(self, cr, uid, ids, context=None):
        _register_log(self, cr, uid, ids, self._name, 'Sign offline', False, True, 'write', context)
        vals = {'signed_off_line': True, 'signature_state': False}
        for sign in self.read(cr, uid, ids, ['allowed_to_be_signed_unsigned', 'doc_locked_for_sign'], context=context):
            if not sign['allowed_to_be_signed_unsigned']:
                raise osv.except_osv(_('Warning'), _("You are not allowed to remove the signature of this document in this state, please refresh the page"))
            if sign['doc_locked_for_sign']:
                self.unlock_doc_for_sign(cr, uid, [sign['id']], context=context)
                _register_log(self, cr, uid, ids, self._name, 'Document locked', True, False, 'write', context)
        self.write(cr, uid, ids, vals, context=context)
        return True

    def activate_offline_reset(self, cr, uid, ids, context=None):
        to_unsign = []
        to_delete = []
        for doc in self.browse(cr, uid, ids, fields_to_fetch=['signature_line_ids'], context=context):
            for line in doc.signature_line_ids:
                if line.signed:
                    to_unsign.append(line.id)
                to_delete.append(line.id)

        if to_unsign:
            # disable check if button has BAR (i.e: uid.realUid exists)
            self.pool.get('signature.line').action_unsign(cr, uid, to_unsign, context=context, check_ur=not hasattr(uid, 'realUid'), check_super_unsign=True)
        if to_delete:
            self.pool.get('signature.line').write(cr, uid, to_delete, {'user_id': False, 'user_name': False},  context=context)

        return self.activate_offline(cr, uid, ids, context=context)

    def disable_offline(self, cr, uid, ids, context=None):
        _register_log(self, cr, uid, ids, self._name, 'Sign offline', True, False, 'write', context)
        self.write(cr, uid, ids, {'signed_off_line': False}, context=context)
        return True

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        fields_to_reset = [
            'signature_id', 'signature_line_ids',
            'signature_state', 'signed_off_line', 'signature_is_closed', 'signature_closed_date',
            'signature_closed_user', 'signature_res_id', 'signature_res_model', 'doc_locked_for_sign'
        ]
        to_del = []
        for ftr in fields_to_reset:
            if ftr not in default:
                to_del.append(ftr)
        res = super(signature_object, self).copy_data(cr, uid, id, default=default, context=context)
        for ftd in to_del:
            if ftd in res:
                del(res[ftd])
        return res

    def create(self, cr, uid, vals, context=None):
        new_id = super(signature_object, self).create(cr, uid, vals, context=context)
        if vals and 'signature_line_ids' not in vals and \
                (list_sign.get(self._name) or self._name in ['account.bank.statement', 'sale.order', 'stock.picking']) and \
                self.pool.get('unifield.setup.configuration').get_config(cr, uid, 'signature') and \
                (self._name != 'stock.picking' or self._name == 'stock.picking' and vals.get('type') in ['in', 'out'] and
                 vals.get('subtype', False) in ['standard', 'picking', False]):

            line_obj = self.pool.get('signature.line')
            ftf = ['signature_id']
            if self._name == 'account.bank.statement':
                ftf += ['local_register', 'journal_id']
            elif self._name == 'account.invoice':
                ftf += ['doc_type']
            elif self._name == 'sale.order':
                ftf += ['procurement_request']
            elif self._name == 'stock.picking':
                ftf += ['type', 'subtype']

            obj = self.browse(cr, uid, new_id, fields_to_fetch=ftf, context=context)

            if self._name == 'account.bank.statement' and not obj.local_register:
                return new_id

            if self._name == 'account.invoice' and obj.doc_type not in ('si', 'donation'):
                return new_id

            if obj.signature_id:
                if self._name == 'account.bank.statement':
                    key = 'account.bank.statement.%s' % obj.journal_id.type
                elif self._name == 'sale.order':
                    key = 'sale.order.%s' % (obj.procurement_request and 'ir' or 'fo')
                elif self._name == 'stock.picking':
                    key = 'stock.picking.%s' % (obj.type == 'out' and (obj.subtype == 'picking' and 'pick' or 'out') or 'in')
                else:
                    key = self._name

                for x in list_sign.get(key):
                    line_obj.create(cr, 1, {
                        'name_key': x[0],
                        'name': x[1],
                        'is_active': x[2],
                        'signature_id': obj.signature_id.id,
                        'prio': x[3],
                    }, context=context)
        return new_id

    def lock_doc_for_sign(self, cr, uid, ids, context=None):
        """
        Allow user to lock the document, but only if at least on signee has been added
        """
        if context is None:
            context = {}
        if not ids:
            return True

        _register_log(self, cr, uid, ids, self._name, 'Document locked', False, True, 'write', context)

        doc = _('document')
        if self._name == 'purchase.order':
            doc = _('PO')
        if not self.read(cr, uid, ids[0], ['signature_state'], context=context)['signature_state']:
            raise osv.except_osv(_('Warning'),
                                 _("In order to lock this %s for signature, signee user(s) should have been added") % (doc,))
        self.write(cr, uid, ids, {'doc_locked_for_sign': True}, context=context)

        return True

    def unlock_doc_for_sign(self, cr, uid, ids, context=None):
        """
        Allow the document to be editable, but un-sign it in the process
        """
        if context is None:
            context = {}

        _register_log(self, cr, uid, ids, self._name, 'Document locked', True, False, 'write', context)

        cr.execute("""
            SELECT sl.id FROM signature_line sl LEFT JOIN signature s ON sl.signature_id = s.id 
            WHERE s.signature_res_model = %s AND s.signature_res_id IN %s AND sl.signed = 't' 
        """, (self._name, tuple(ids)))
        to_unsign = []
        for x in cr.fetchall():
            to_unsign.append(x[0])
        if to_unsign:
            self.pool.get('signature.line').super_action_unsign(cr, uid, to_unsign, context=context)

        self.write(cr, uid, ids, {'doc_locked_for_sign': False}, context=context)

        return True


signature_object()


class signature_line(osv.osv):
    _name = 'signature.line'
    _description = 'Document line to sign by role'
    _order = 'prio, id'

    def _format_state_value(self, cr, uid, ids, name=None, arg=None, context=None):
        res = {}
        user_lang = self.pool.get('res.users').read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
        lang_obj = self.pool.get('res.lang')
        lang_id = lang_obj.search(cr, uid, [('code', '=', user_lang)])[0]

        cache_state = {}
        for x in self.browse(cr, uid, ids, fields_to_fetch=['signed', 'value', 'unit', 'doc_state', 'signature_id'], context=context):
            if not x.signed:
                res[x.id] = {'format_value': False, 'format_state': False}
            else:
                if x.value is not False:
                    res[x.id] = {'format_value': '%s %s' % (lang_obj.format(cr, uid, [lang_id], '%.2lf', x.value, grouping=True, monetary=True),  x.unit)}
                else:
                    res[x.id] = {'format_value': x.unit}

                doc_state = x.doc_state
                key = '%s-%s' % (x.signature_id.signature_res_model, doc_state)
                if key not in cache_state:
                    field = 'state'
                    # To display OUT Delivered/Received states
                    if x.signature_id.signature_res_model == 'stock.picking':
                        p_data = self.pool.get('stock.picking').read(cr, uid, x.signature_id.signature_res_id,
                                                                     ['type', 'subtype', 'delivered'], context=context)
                        if p_data['type'] == 'out' and p_data['subtype'] == 'standard':
                            if doc_state == 'done':
                                if p_data['delivered']:
                                    doc_state = 'received'
                                else:
                                    doc_state = 'dispatched'
                            elif doc_state == 'delivered':
                                doc_state = 'received'
                            field = 'state_hidden'
                    cache_state[key] = self.pool.get('ir.model.fields').get_selection(cr, uid, x.signature_id.signature_res_model, field, doc_state, context=context)
                res[x.id]['format_state'] = cache_state[key]
        return res


    def _get_ready_to_sign(self, cr, uid, ids, name=None, arg=None, context=None):
        if not ids:
            return {}
        ret = {}
        for _id in ids:
            ret[_id] = False

        cr.execute('''
            select
                l.id
            from
                signature_line l
            left join
                signature_line other on other.signature_id = l.signature_id and other.is_active='t' and other.prio < l.prio and other.signed = 'f'
            where
                l.id in %s and
                l.is_active = 't' and
                l.signed = 'f'
            group by
                l.id
            having
                count(other.id) = 0
        ''', (tuple(ids), ))
        for _id in cr.fetchall():
            ret[_id[0]] = True
        return ret

    _columns = {
        'signature_id': fields.many2one('signature', 'Parent', required=1, select=1),
        'user_id': fields.many2one('res.users', 'Signee User'),
        'legal_name': fields.char('Legal name', size=64),
        'user_name': fields.char('User name', size=64),
        'is_active': fields.boolean('Active'),
        'name': fields.char('Role/Function', size=128),
        'name_key': fields.char('key', size=10),
        'signed': fields.boolean('Signed'),
        'image_id': fields.many2one('signature.image', 'Image'),
        'image': fields.related('image_id', 'pngb64', type='text', string='Signature', readonly=1),
        'data_image': fields.related('image_id', 'image', type='text', string='Signature', readonly=1),
        'date': fields.datetime('Date'),
        'doc_state': fields.char('Doc State at signature date', size=64, readonly=1),
        'value': fields.float_null('Value', digits=(16,2)),
        'unit': fields.char('Unit', size=16),
        'format_value': fields.function(_format_state_value, method=1, type='char', string='Value', multi='fsv'),
        'format_state': fields.function(_format_state_value, method=1, type='char', string='Document State', multi='fsv'),
        'backup': fields.boolean('Back Up', readonly=1),
        'prio': fields.integer('Sign Order', readonly=1, select=1),
        'ready_to_sign': fields.function(_get_ready_to_sign, type='boolean', string='Ready to sign', method=1),
    }

    _defaults = {
        'signed': False,
        'prio': 0,
    }

    _sql_constraints = [
        ('unique_signature_name_key', 'unique (signature_id,name_key)', 'Unique signature_id,name_key')
    ]

    def _check_sign_unsign(self, cr, uid, ids, check_has_sign=False, check_unsign=False, check_super_unsign=False, context=None):
        # to export the term used in report
        _('As back up of ')

        assert len(ids) < 2, '_check_sign_unsign: only 1 id is allowed'
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid

        user_obj = self.pool.get('res.users')
        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'user_id', 'ready_to_sign'], context=context)
        if not check_super_unsign and real_uid != sign_line.user_id.id:
            raise osv.except_osv(_('Warning'), _("You are not allowed to sign on this line - please contact the document creator"))

        if sign_line.signature_id.signature_is_closed:
            raise osv.except_osv(_('Warning'), _("Signature Closed."))

        if check_unsign and not sign_line.signature_id.allowed_to_be_signed_unsigned:
            raise osv.except_osv(_('Warning'), _("You are not allowed to remove the signature of this document in this state, please refresh the page"))

        if check_super_unsign:
            group_name = ''
            if sign_line.signature_id.signature_res_model in ['account.invoice', 'account.bank.statement']:
                group_name = 'Sign_document_creator_finance'
            elif sign_line.signature_id.signature_res_model in ['purchase.order', 'stock.picking', 'sale.order']:
                group_name = 'Sign_document_creator_supply'
            if not group_name or (group_name and not user_obj.check_user_has_group(cr, uid, group_name)):
                raise osv.except_osv(_('Warning'), _("You are not allowed to remove this signature"))
            if not sign_line.signature_id.allowed_to_be_signed_unsigned:
                raise osv.except_osv(_('Warning'), _("You are not allowed to remove the signature of this document in this state, please refresh the page"))

        if check_has_sign:
            if not sign_line.ready_to_sign:
                raise osv.except_osv(_('Warning'), _("You cannot sign before other role(s)"))
            if not sign_line.signature_id.allowed_to_be_signed_unsigned:
                raise osv.except_osv(_('Warning'), _("You are not allowed to sign this document in this state, please refresh the page"))

            user_d = user_obj.browse(cr, uid, real_uid, fields_to_fetch=['has_valid_signature', 'esignature_id'], context=context)
            if not user_d.has_valid_signature:
                raise osv.except_osv(_('Warning'), _("No signature defined in user's profile"))
            return user_d.esignature_id

        return True

    def open_sign_wizard(self, cr, uid, ids, context=None):
        esignature = self._check_sign_unsign(cr, uid, ids, check_has_sign=True, context=context)
        line = self.browse(cr, uid, ids[0], context=context)
        doc = self.pool.get(line.signature_id.signature_res_model).browse(cr, uid, line.signature_id.signature_res_id, context=context)

        image = esignature.pngb64

        unit = saved_unit[line.signature_id.signature_res_model](doc)
        value = saved_value[line.signature_id.signature_res_model](doc)
        doc_state = saved_state[line.signature_id.signature_res_model](doc)
        if value is not False:
            name = '%s %g %s' % (saved_name[line.signature_id.signature_res_model](doc), value, unit or '')
        else:
            name = '%s %s' % (saved_name[line.signature_id.signature_res_model](doc), unit or '')

        wiz_id = self.pool.get('signature.document.wizard').create(cr, uid, {
            'name': name,
            'unit': unit,
            'value': value,
            'user_id': hasattr(uid, 'realUid') and uid.realUid or uid,
            'role': line.name,
            'line_id': line.id,
            'doc_state': doc_state,
            'image': image,
            'backup': line.backup,
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'signature.document.wizard',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
        }


    def action_sign(self, cr, uid, ids, value, unit, doc_state, context=None):

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'name'], context=context)
        esignature = sign_line._check_sign_unsign(check_has_sign=True, context=context)
        user = self.pool.get('res.users').browse(cr, uid, real_uid, fields_to_fetch=['name'], context=context)

        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        self.write(cr, root_uid, ids, {'signed': True, 'date': fields.datetime.now(), 'user_id': real_uid, 'image_id': esignature.id, 'value': value, 'unit': unit, 'legal_name': esignature.legal_name, 'user_name': user.name, 'doc_state': doc_state}, context=context)

        if value is False:
            value = ''
        new = "signed by %s, %s %s" % (user.name, value, unit)
        desc = "Signature added on role %s" % (sign_line.name, )
        _register_log(self, cr, real_uid, sign_line.signature_id.signature_res_id, sign_line.signature_id.signature_res_model, desc, '', new, 'create', context)
        self.pool.get('signature')._set_signature_state(cr, root_uid, [sign_line.signature_id.id], context=context)
        return True

    def super_action_unsign(self, cr, uid, ids, context=None):
        '''
        To allow the users in the groups Sign_document_creator_finance and/or Sign_document_creator_supply to remove
        signatures they haven't signed
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        return self.action_unsign(cr, uid, ids, context=context, check_ur=True, check_super_unsign=True)

    def action_unsign(self, cr, uid, ids, context=None, check_ur=True, check_super_unsign=False):
        '''
        check_ur: used when sign offline by sign creator
        '''
        sign_lines = self.browse(cr, uid, ids, fields_to_fetch=['signature_id', 'name', 'user_name', 'value', 'unit'], context=context)
        sign_line = sign_lines[0]
        if check_ur:
            sign_line._check_sign_unsign(check_unsign=True, check_super_unsign=check_super_unsign, context=context)

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        value = sign_line.value
        if value is False:
            value = ''
        if len(sign_lines) > 1:
            signers = []
            for s_line in sign_lines:
                signers.append('%s (%s)' % (s_line.name, s_line.user_name))
            old = ', '.join(signers)
            desc = 'All Signatures removed'
        else:
            old = "signed by %s, %s %s" % (sign_line.user_name, value, sign_line.unit)
            desc = 'Delete signature on role %s' % (sign_line.name, )
        _register_log(self, cr, real_uid, sign_line.signature_id.signature_res_id, sign_line.signature_id.signature_res_model, desc, old, '', 'unlink', context)

        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        self.write(cr, root_uid, ids, {'signed': False, 'date': False, 'image_id': False, 'value': False, 'unit': False, 'legal_name': False, 'doc_state': False}, context=context)
        self.pool.get('signature')._set_signature_state(cr, root_uid, [sign_line.signature_id.id], context=context)

        return True


signature_line()


class signature_image(osv.osv):
    _name = 'signature.image'
    _description = "Image of user signature in png"
    _rec_name = 'user_id'
    _order = 'id desc'

    def _get_image(self, cr, uid, ids, name=None, arg=None, context=None):
        res = {}
        for u in self.browse(cr, uid, ids, fields_to_fetch=['image'], context=context):
            if u.image:
                res[u.id] = u.image.split(',')[-1]
            else:
                res[u.id] = False
        return res

    def name_get(self, cr, uid, ids, context=None):
        ret = []
        for img in self.browse(cr, uid, ids, fields_to_fetch=['user_name'], context=context):
            ret.append((img.id, '%s (id:%s)' % (img.user_name, img.id)))

        return ret

    def _get_is_active(self, cr, uid, ids, name=None, arg=None, context=None):
        res = {}
        today = fields.date.today()
        for s in self.browse(cr, uid, ids, fields_to_fetch=['from_date', 'to_date', 'inactivation_date'], context=context):
            if s.inactivation_date or not s.from_date:
                res[s.id] = False
            elif s.to_date:
                res[s.id] = today >= s.from_date and today <= s.to_date
            else:
                res[s.id] = today >= s.from_date
        return res

    _columns = {
        'user_id': fields.many2one('res.users', required=1, string='User', domain=[('has_sign_group', '=', True)]),
        'login': fields.related('user_id', 'login', type='char', size=64, string='Login', readonly=1),
        'legal_name': fields.char('Legal name', size=64),
        'user_name': fields.char('User name', size=64),
        'image': fields.text('Signature'),
        'pngb64': fields.function(_get_image, method=1, type='text', string='Image'),
        'from_date': fields.date('Start Date', readonly=True),
        'to_date': fields.date('End Date', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),
        'inactivation_date': fields.datetime('Inactivation Date', readonly=True),
        'is_active': fields.function(_get_is_active, method=1, type='boolean', string='Active'),
    }


signature_image()

class signature_document_wizard(osv.osv_memory):
    _name = 'signature.document.wizard'
    _description = 'Wizard used to sign a document'
    _columns = {
        'name': fields.char('Document', size=256, readonly=1),
        'user_id': fields.many2one('res.users', 'Users', readonly=1),
        'user_name': fields.related('user_id', 'name', type='char', size=64, string='User Name', readonly=1),
        'role': fields.char('Role/Function', size=256, readonly=1),
        'line_id': fields.many2one('signature.line', 'Line', readonly=1),
        'image': fields.text('Signature', readonly=1),
        'value': fields.float('Value', digits=(16, 2)),
        'unit': fields.char('Unit', size=16),
        'doc_state': fields.char('Doc state', size=64),
        'backup': fields.boolean('Back up', readonly=1),
    }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        self.pool.get('signature.line').action_sign(cr, uid, [wiz.line_id.id], wiz.value, wiz.unit, wiz.doc_state, context=context)
        return {'type': 'ir.actions.act_window_close', 'o2m_refresh': 'signature_line_ids'}

signature_document_wizard()


class signature_add_user_wizard(osv.osv_memory):
    _name = 'signature.add_user.wizard'
    _description = 'Wizard used on document to add users allowed to sign'

    _max_role = 5
    _columns = {
        'name': fields.char('Document', size=256, readonly=1),
        'signature_id': fields.many2one('signature', readonly=1),
        'doc_locked_for_sign': fields.boolean('Document is locked because of signature', readonly=True),
    }

    def __init__(self, pool, cr):

        for x in range(0, self._max_role):
            self._columns.update({
                'line_id_%d' % x: fields.many2one('signature.line',  'Signature Line', readonly=1),
                'role_%d' % x: fields.char('Role', size=256, readonly=1),
                'active_%d' % x: fields.boolean('Active'),
                'backup_%d' % x: fields.boolean('Back up'),
                'legal_name_%d' % x: fields.char('Legal Name', size=256, readonly=1),
                'login_%d' % x: fields.many2one('res.users', 'Login', domain=[('signature_enabled', '=', True)], context={'from_sign_view': True}),
                'username_%d' % x: fields.char('Username', size=256, readonly=1),
                'signed_%d' % x: fields.boolean('Signed'),
            })
        super(signature_add_user_wizard, self).__init__(pool, cr)

    def change_user(self, cr, uid, ids, user_id, row, doc_locked_for_sign, context=None):
        values = {
            'legal_name_%s' % row: False,
            'username_%s' % row: False,
        }
        if user_id:
            u = self.pool.get('res.users').browse(cr, uid, user_id, fields_to_fetch=['login', 'esignature_id'], context=context)
            values['legal_name_%s' % row] = u.esignature_id and u.esignature_id.legal_name or ''
            values['username_%s' % row] = u.login
        elif doc_locked_for_sign:
            addu_wiz = self.read(cr, uid, ids[0], ['login_%s' % row], context=context)
            return {
                'value': {'login_%s' % row: addu_wiz['login_%s' % row]},
                'warning': {'title': _('Warning!'), 'message': _('You can not remove a signee if the document is locked')}
            }

        return {'value': values}

    def change_active(self, cr, uid, ids, active, row, context=None):
        if not active:
            return {
                'value':  {
                    'legal_name_%s' % row: False,
                    'username_%s' % row: False,
                    'backup_%s' % row: False,
                    'login_%s' % row: False,
                }
            }


        return {}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view = super(signature_add_user_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if context is None:
            context = {}

        if view_type == 'form' and context.get('wiz_id'):
            arch = etree.fromstring(view['arch'])

            wiz = self.browse(cr, uid, context['wiz_id'], context=context)
            added = """<group colspan="4" col="12">
                <separator string="%(Role)s" colspan="2" />
                <separator string="%(Active)s" colspan="2" halign="center" />
                <separator string="%(User)s" colspan="2" />
                <separator string="%(Back up)s" colspan="2" halign="center" />
                <separator string="%(Login)s" colspan="2" />
                <separator string="%(Legal Name)s" colspan="2" />
            """ % {
                'Role': escape_html(_('Role')),
                'Active': escape_html(_('Active')),
                'User': escape_html(_('User')),
                'Back up': escape_html(_('Back up')),
                'Login': escape_html(_('Login')),
                'Legal Name': escape_html(_('Legal Name')),
            }
            for x in range(0, self._max_role):
                if wiz['role_%d' % x]:
                    if wiz['signed_%d' % x]:
                        readonly = 'readonly="1"'
                        attr_ro = readonly
                    else:
                        readonly = ""
                        attr_ro = """ attrs="{'readonly': [('active_%d', '=',False)]}" """ % x

                    added += """
                        <field name="role_%(x)d" colspan="2" nolabel="1" />
                        <field name="active_%(x)d" colspan="2" nolabel="1" halign="center" on_change="change_active(active_%(x)d, '%(x)d')" %(readonly)s/>
                        <field name="login_%(x)d" colspan="2" nolabel="1" on_change="change_user(login_%(x)d, '%(x)d', doc_locked_for_sign)" %(attr_ro)s />
                        <field name="backup_%(x)d" colspan="2" nolabel="1" halign="center" %(attr_ro)s />
                        <field name="username_%(x)d" colspan="2" nolabel="1" />
                        <field name="legal_name_%(x)d" colspan="2" nolabel="1" />
                    """ % {'x': x, 'attr_ro': attr_ro, 'readonly': readonly}

            added += "</group>"
            added_etree = etree.fromstring(added)
            fields = arch.xpath('//group[@name="list_values"]')
            parent_node = fields[0].getparent()
            parent_node.remove(fields[0])
            parent_node.append(added_etree)

            xarch, xfields = super(signature_add_user_wizard, self)._view_look_dom_arch(cr, uid, arch, view_id, context=context)

            view['arch'] = xarch
            view['fields'] = xfields

        return view

    def save(self, cr, uid, ids, context=None):
        signature_obj = self.pool.get('signature')
        line_sign_obj = self.pool.get('signature.line')

        wiz = self.browse(cr, uid, ids[0], context=context)
        data = {}

        fake_uid = uid
        rules_pool = self.pool.get('msf_button_access_rights.button_access_rule')
        rule_ids = rules_pool.search(cr, 1, [('name', '=', 'add_user_signatures'), ('model_id', '=', wiz.signature_id.signature_res_model)])
        if rule_ids:
            user_group = set(self.pool.get('res.users').read(cr, 1, uid, ['groups_id'])['groups_id'])
            for rule in rules_pool.browse(cr, 1, rule_ids, fields_to_fetch=['group_ids']):
                if user_group.intersection([g.id for g in rule.group_ids]):
                    fake_uid = fakeUid(1, uid)
                    break

        nb_set = 0
        for x in range(0, self._max_role):
            if not wiz['line_id_%d' %x]:
                continue

            if wiz['line_id_%d' %x].signed:
                nb_set += 1
                continue

            if not wiz['active_%d' %x]:
                line_data = {
                    'user_id': False,
                    'backup':  False,
                    'user_name': False,
                    'is_active': False,
                }
            else:
                line_data = {
                    'user_id': wiz['login_%d' %x].id,
                    'backup':  wiz['backup_%d' %x] or False,
                    'user_name': wiz['login_%d' %x].name,
                    'is_active': True,
                }
            if line_data['is_active'] != wiz['line_id_%d' %x].is_active:
                _register_log(self, cr, uid, wiz.signature_id.signature_res_id, wiz.signature_id.signature_res_model,
                              'Signature active on role %s' % (wiz['line_id_%d' %x].name, ),
                              '%s'%(wiz['line_id_%d' %x].is_active, ),
                              '%s'%(line_data['is_active'], ),
                              'write', context
                              )

            if line_data['user_id'] != wiz['line_id_%d' %x].user_id.id:
                _register_log(self, cr, uid, wiz.signature_id.signature_res_id, wiz.signature_id.signature_res_model,
                              'User Allowed to sign on %s' % wiz['line_id_%d' %x].name,
                              '%s %s' % (wiz['line_id_%d' %x].user_id.login or '', wiz['line_id_%d' %x].user_id and wiz['line_id_%d' %x].user_id.esignature_id and wiz['line_id_%d' %x].user_id.esignature_id.legal_name or ''),
                              '%s %s' % (wiz['login_%d' %x].login or '', wiz['login_%d' %x].esignature_id and wiz['login_%d' %x].esignature_id.legal_name or ''),
                              'write', context
                              )
            if line_data['backup'] != wiz['line_id_%d' %x].backup:
                _register_log(self, cr, uid, wiz.signature_id.signature_res_id, wiz.signature_id.signature_res_model,
                              'Sign backup on %s (%s)' % (wiz['line_id_%d' %x].name, wiz['login_%d' %x].login or ''),
                              wiz['line_id_%d' %x].backup,
                              line_data['backup'],
                              'write', context
                              )

            line_sign_obj.write(cr, fake_uid, wiz['line_id_%d' %x].id, line_data, context=context)
            if wiz['login_%d' %x]:
                nb_set += 1

        if wiz.signature_id.signature_state == 'open' and not nb_set:
            data['signature_state'] = False
        elif wiz.signature_id.signature_state not in ('partial', 'signed') and nb_set:
            data['signature_state'] = 'open'

        if data:
            previous_state = wiz.signature_id.signature_state
            signature_obj._log_sign_state(cr, uid, wiz.signature_id.signature_res_id, wiz.signature_id.signature_res_model, previous_state, data['signature_state'], context)
            signature_obj.write(cr, fake_uid, wiz.signature_id.id, data, context=context)

        return {'type': 'ir.actions.act_window_close'}


    def cancel(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}


signature_add_user_wizard()

class signature_set_user(osv.osv_memory):
    _name = 'signature.set_user'
    _description = "Wizard to add new signature on user profile"
    _rec_name = 'user_id'

    def _get_b64(self,cr, uid, ids, name=None, arg=None, context=None):
        ret = {}
        for x in self.browse(cr, uid, ids, fields_to_fetch=['new_signature'], context=context):
            ret[x.id] = False
            if x.new_signature:
                ret[x.id] = x.new_signature.split(',')[-1]
        return ret

    _columns = {
        'b64_image': fields.function(_get_b64, method=1, type='text', string='New Signature'),
        'new_signature': fields.text("Draw your signature"),
        'json_signature': fields.text('Json Signature'),
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'user_name': fields.related('user_id', 'name', type='char', string='User', readonly=1),
        'preview': fields.boolean('Preview'),
        'legal_name': fields.char('Legal Name', size=128, required=1),
        'position': fields.selection([('top', 'Top'), ('middle', 'Middle'), ('bottom', 'Bottom')], string='Position'),
    }

    #def _get_name(self, cr, uid, *a, **b):
    #    real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
    #    return self.pool.get('res.users').browse(cr, uid, real_uid, fields_to_fetch=['name']).name

    _defaults = {
        'preview': False,
        'position': 'bottom',
        #'legal_name': lambda self, cr, uid, *a, **b: self._get_name(cr, uid, *a, **b),
    }
    def closepref(self, cr, uid, ids, context=None):
        return {'type': 'closepref'}

    def previous(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
            'opened': True
        }

    def preview(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        if not wiz.new_signature:
            return {'type': 'closepref'}

        msg = ustr(wiz.legal_name)

        # Add legal name to signature
        image = Image.open(BytesIO(base64.b64decode(wiz.b64_image)))
        W, H = image.size
        fit = False
        init_font_size = 28
        font_size = init_font_size
        while not fit and font_size > 3:
            font_path = customfonts.GetFontPath('DejaVuSans.ttf')
            font = ImageFont.truetype(font_path, font_size)
            left, top, w,h = font.getbbox(msg)
            fit = w <= W
            font_size -= 1
        new_img = Image.new("RGBA", (W, H+init_font_size))
        new_img.paste(image, (0, 0))
        draw = ImageDraw.Draw(new_img)
        # H-5 to emulate anchor='md' which does not work on this PIL version
        draw.text(((W-w)/2,H-5), msg, font=font, fill="black")
        txt_img = BytesIO()
        new_img.save(txt_img, 'PNG')
        wiz.write({'new_signature': 'data:image/png;base64,%s' % str(base64.b64encode(txt_img.getvalue()), 'utf8')}, context=context)


        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'signature_set_user_form_preview')
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': wiz.id,
            'view_id': [view_id[1]],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
            'opened': True
        }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid

        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        if wiz.new_signature:
            if wiz.user_id.esignature_id:
                self.pool.get('res.users')._archive_signature(cr, root_uid, [real_uid], context=context)

            new_image = self.pool.get('signature.image').create(cr, root_uid, {
                'user_id': real_uid,
                'image': wiz.new_signature,
                'legal_name': wiz.legal_name,
                'user_name': wiz.user_id.name,
                'from_date': wiz.user_id.signature_from,
                'to_date': wiz.user_id.signature_to,
            }, context=context)
            self.pool.get('res.users').write(cr, root_uid, real_uid, {'esignature_id': new_image}, context=context)

        return {'type': 'ir.actions.act_window_close'}

signature_set_user()


class signature_change_date(osv.osv_memory):
    _name = 'signature.change_date'
    _rec_name = 'user_id'
    _description = "Change Dates on user's signature"

    _columns = {
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'current_from': fields.date('Current Date From', readonly=1),
        'current_to': fields.date('Current Date To', readonly=1),
        'new_to': fields.date('New Date To'),
    }

    def change_new_to(self, cr, uid, ids, current_from, new_to, context=None):
        if not new_to:
            return {}

        if new_to < current_from:
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _('New Date To can not be before Date From')
                }
            }
        current_sign = self.browse(cr, uid, ids[0], context=context).user_id.esignature_id
        if current_sign:
            sign_line_obj = self.pool.get('signature.line')
            line_id = sign_line_obj.search(cr, uid, [('image_id', '=', current_sign.id), ('date', '>=', new_to)], order='date desc', limit=1, context=context)
            if line_id:
                sign_line = sign_line_obj.browse(cr, uid, line_id[0], context=context)
                last_date = datetime.strptime(sign_line.date, '%Y-%m-%d %H:%M:%S')
                date_lang_format = self.pool.get('date.tools').get_datetime_format(cr, uid, context=context)
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('Last document signed on %s, Date To can not be before.') % (ustr(last_date.strftime(date_lang_format)),)
                    },
                    'value': {
                        'new_to': (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                    }
                }

        return {}

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        if wiz.new_to and wiz.new_to < wiz.current_from:
            raise osv.except_osv(_('Warning'), _('Date To can not be before Date From'))

        self.pool.get('res.users').write(cr, uid, wiz.user_id.id, {'signature_to': wiz.new_to}, context=context)
        self.pool.get('signature.image').write(cr, uid, wiz.user_id.esignature_id.id, {'to_date': wiz.new_to}, context=context)

        return {'type': 'ir.actions.act_window_close'}

signature_change_date()

class signature_setup(osv.osv_memory):
    _name = 'signature.setup'
    _inherit = 'res.config'

    _columns = {
        'signature': fields.boolean(string='Activate Electronic Validation ?'),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        """
        if context is None:
            context = {}
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(signature_setup, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        res['signature'] = setup.signature
        return res

    def execute(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not isinstance(ids, list) or len(ids) != 1:
            raise osv.except_osv(_('Error'), _('An error has occurred with the item retrieved from the form. Please contact an administrator if the problem persists.'))
        wiz = self.browse(cr, uid, ids[0], fields_to_fetch=['signature'], context=context)
        setup_obj = self.pool.get('unifield.setup.configuration')
        setup = setup_obj.get_config(cr, uid)
        if setup:
            if not wiz.signature:
                user_ids = self.pool.get('res.users').search(cr, uid, [('signature_enabled', '=', True)], context=context)
                if user_ids:
                    user_data = [u['login'] for u in self.pool.get('res.users').read(cr, uid, user_ids[0:5], ['login'], context=context)]
                    if len(user_ids) > 5:
                        user_data.append('...')
                    raise osv.except_osv(_('Warning'), _('Signature cannot be deactivated: it is enabled on %d user(s). Please untick "Enable Signature" on users: %s') % (len(user_ids), ', '.join(user_data)))

            for module, xmlid in [('useability_dashboard_and_menu', 'signature_follow_up_menu'), ('base', 'signature_image_menu'), ('useability_dashboard_and_menu', 'my_signature_menu')]:
                menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, xmlid)[1]
                self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': wiz.signature}, context=context)

            if wiz.signature:
                for obj in list_sign:
                    if obj == 'purchase.order':
                        cond = "purchase_order o where o.signature_id is not null and o.rfq_ok='f'"
                    elif obj.startswith('sale.order'):
                        is_ir = obj.split('.')[-1] == 'ir' or False
                        cond = "sale_order o where o.signature_id is not null and o.procurement_request=%s" % (is_ir,)
                    elif obj.startswith('account.bank.statement'):
                        obj_typ = obj.split('.')[-1]
                        cond = "account_bank_statement o, account_journal j, res_company c where o.journal_id = j.id and o.signature_id is not null and j.type ='%s' and c.instance_id = j.instance_id" % (obj_typ, )
                    elif obj == 'account.invoice':
                        cond = "account_invoice o where o.signature_id is not null and o.real_doc_type in ('donation', 'si') or (o.real_doc_type is null and o.type='in_invoice' and o.is_direct_invoice='f' and o.is_inkind_donation='f' and o.is_debit_note='f' and o.is_intermission='f') or (o.real_doc_type is null and o.type='in_invoice' and o.is_debit_note='f' and o.is_inkind_donation='t')"
                    elif obj.startswith('stock.picking'):
                        obj_type, obj_subtype = 'in', 'standard'
                        if obj.split('.')[-1] == 'pick':
                            obj_type, obj_subtype = 'out', 'picking'
                        elif obj.split('.')[-1] == 'out':
                            obj_type = 'out'
                        cond = "stock_picking o where o.signature_id is not null and o.type='%s' and o.subtype='%s'" % (obj_type, obj_subtype)
                    elif obj == 'physical.inventory':
                        cond = "physical_inventory o where o.signature_id is not null"

                    for role in list_sign[obj]:
                        cr.execute("""
                            insert into signature_line (signature_id, is_active, name, name_key, prio, signed)
                                    select o.signature_id, %%(is_active)s, %%(name)s, %%(name_key)s, %%(prio)s, 'f' from
                                    %s
                            on conflict on constraint signature_line_unique_signature_name_key do nothing
                        """ % cond, { # not_a_user_entry
                            'is_active': role[2],
                            'name': role[1],
                            'name_key': role[0],
                            'prio': role[3],
                        })
            setup_obj.write(cr, uid, [setup.id], {'signature': wiz.signature}, context=context)

signature_setup()

class signature_export_wizard(osv.osv_memory):
    _name = 'signature.export.wizard'
    _description = 'Wizard to export signatures'
    _rec_name = 'start_date'

    _columns = {
        'start_date': fields.date('Start Date', required=1),
        'end_date': fields.date('End Date', required=1),
    }

    _defaults = {
        'start_date': lambda *a: fields.date.today(),
    }

    def export(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        if wiz.start_date > wiz.end_date:
            raise osv.except_osv(_('Warning'), _('Start Date must be before End Date'))
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'signature.export.report',
            'context': context,
        }

signature_export_wizard()
