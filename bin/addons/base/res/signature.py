# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.translate import _
from tools import ustr
from tools.misc import fakeUid
from lxml import etree
from datetime import datetime
from datetime import timedelta

from report.render.rml2pdf import customfonts
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO

list_sign = {
    'purchase.order': [
        # (key, label, active, subtyp)
        ('sr', _('Supply Responsible'), True, ''),
        ('tr', _('Technical Responsible'), True, ''),
        ('fr', _('Finance Responsible'), True, ''),
        ('mr', _('Mission Responsible'), False, ''),
        ('hq', _('HQ'), False, ''),
    ],
    'sale.order': [
        ('tr', _('Technical Responsible'), True, ''),
        ('sr', _('Supply Responsible'), True, ''),
    ],
    'account.bank.statement.cash': [
        ('fr', _('Signature 1 - reconciliation'), True, 'rec'),
        ('mr', _('Signature 2 - reconciliation'), True, 'rec'),
        ('fr_report', _('Signature 1 - full report'), True, 'full'),
        ('mr_report', _('Signature 2 - full report'), True, 'full'),
    ],
    'account.bank.statement.bank': [
        ('fr', _('Signature 1 - reconciliation'), True, 'rec'),
        ('mr', _('Signature 2 - reconciliation'), True, 'rec'),
        ('fr_report', _('Signature 1 - full report'), True, 'full'),
        ('mr_report', _('Signature 2 - full report'), True, 'full'),
    ],
    'account.bank.statement.cheque': [
        ('fr_report', _('Signature 1 - full report'), True, ''),
        ('mr_report', _('Signature 2 - full report'), True, ''),
    ],
    'account.invoice': [
        ('sr', _('Supply Responsible'), True, ''),
        ('tr', _('Technical Responsible'), True, ''),
        ('fr', _('Finance Responsible'), True, ''),
        ('mr', _('Mission Responsible'), False, ''),
    ],
    'stock.picking': [
        ('tr', _('Receiver'), True, ''),
        ('sr', _('Controller'), True, ''),
    ],
}

saved_name = {
    'purchase.order': lambda doc: doc.name,
    'sale.order': lambda doc: doc.name,
    'account.bank.statement': lambda doc: '%s %s' %(doc.journal_id.code, doc.period_id.name),
    'account.invoice': lambda doc: doc.name or doc.number,
    'stock.picking': lambda doc: doc.name,
}
saved_value = {
    'purchase.order': lambda doc: round(doc.amount_total, 2),
    'sale.order': lambda doc: round(doc.ir_total_amount, 2),
    'account.bank.statement': lambda doc: doc.journal_id.type in ('bank', 'cheque') and round(doc.balance_end, 2) or doc.journal_id.type == 'cash' and round(doc.msf_calculated_balance, 2) or 0,
    'account.invoice': lambda doc: round(doc.amount_total, 2),
    'stock.picking': lambda doc: False,
}

saved_unit = {
    'purchase.order': lambda doc: doc.currency_id.name,
    'sale.order': lambda doc: doc.functional_currency_id.name,
    'account.bank.statement': lambda doc: doc.currency.name,
    'account.invoice': lambda doc: doc.currency_id.name,
    'stock.picking': lambda doc: doc.total_qty_str,
}

saved_state = {
    'purchase.order': lambda doc: doc.state,
    'sale.order': lambda doc: doc.state,
    'account.bank.statement': lambda doc: doc.state,
    'account.invoice': lambda doc: doc.state,
    'stock.picking': lambda doc: doc.state,
}

def _register_log(self, cr, uid, res_id, res_model, desc, old, new, log_type, context=None):
    audit_line_obj = self.pool.get('audittrail.log.line')
    audit_rule_obj = self.pool.get('audittrail.rule')

    model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', res_model)], context=context)[0]

    root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
    user_uid = hasattr(uid, 'realUid') and uid.realUid or uid
    if isinstance(res_id, int):
        res_id = [res_id]


    for _id in res_id:
        audit_line_obj.create(cr, root_uid, {
            'description': desc,
            'name': desc,
            'log': audit_rule_obj.get_sequence(cr, uid, res_model, _id, context=context),
            'object_id': model_id,
            'user_id': user_uid,
            'method': log_type,
            'res_id': _id,
            'new_value': new,
            'new_value_text': '%s' % new,
            'old_value': old,
            'old_value_text': '%s' % old,
            'field_description': desc,
        }, context=context)

class signature_users_allowed(osv.osv):
    _name = 'signature.users.allowed'
    _rec_name = 'signature_id'
    _description = 'Users Allowed to Sign on document'

    _doc_subtype = [('full', 'Full Report'), ('rec', 'Reconciliation')]
    _columns = {
        'signature_id': fields.many2one('signature','Document', required=1, ondelete='cascade'),
        'user_id': fields.many2one('res.users', 'User', required=1),
        'subtype': fields.selection(_doc_subtype, string='Subtype'),
    }

    _sql_constraints = [
        ('unique_signature_user_subtype,', 'unique(signature_id, user_id, subtype)', 'Triplet must be unique'),
    ]

    _defaults = {
        'subtype': '',
    }

signature_users_allowed()


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

    _columns = {
        'signature_user_ids': fields.one2many('signature.users.allowed', 'signature_id', 'Users allowed to sign'),
        'signature_line_ids': fields.one2many('signature.line', 'signature_id', 'Lines'),
        'signature_res_model': fields.char('Model', size=254, index=1),
        'signature_res_id': fields.integer('Id', index=1),
        'signature_state': fields.selection([('open', 'Open'), ('partial', 'Partially Signed'), ('signed', 'Fully Signed')], string='Signature State', readonly=True),
        'signed_off_line': fields.boolean('Signed Off Line'),
        'signature_is_closed': fields.boolean('Signature Closed', readonly=True),
        'signature_available': fields.function(_get_signature_available, type='boolean', string='Signature Available', method=1),
        'signature_closed_date': fields.datetime('Date of signature closure', readonly=1),
        'signature_closed_user': fields.many2one('res.users', 'Closed by', readonly=1),
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

    _columns = {
        'signature_id': fields.many2one('signature', 'Signature', required=True, ondelete='cascade'),
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

        ftf = ['signature_id', 'signature_res_model']
        if self._name == 'account.bank.statement':
            ftf += ['journal_id']
        doc = self.browse(cr, uid, ids[0], fields_to_fetch=ftf, context=context)

        wiz_data = {
            'name': doc_name,
            'signature_id': doc.signature_id.id,
            'res_users_rec': [(6, 0, [])],
            'res_users_full': [(6, 0, [])],
        }
        if doc.signature_res_model == 'account.bank.statement' and doc.journal_id.type != 'cheque':
            wiz_data['num_col'] = 2
            for user in doc.signature_id.signature_user_ids:
                if user.subtype == 'rec':
                    wiz_data['res_users_rec'][0][2].append(user.user_id.id)
                else:
                    wiz_data['res_users_full'][0][2].append(user.user_id.id)
            view_id = [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'signature_add_user_register_wizard_form')[1]]
        else:
            wiz_data['num_col'] = 1
            wiz_data['res_users'] = [(6, 0, [x.user_id.id for x in doc.signature_id.signature_user_ids])]
            wiz_id = self.pool.get('signature.add_user.wizard').create(cr, uid, {
                'name': doc_name,
                'signature_id': doc.signature_id.id,
                'res_users': [(6, 0, [x.user_id.id for x in doc.signature_id.signature_user_ids])],
            }, context=context)
            view_id = []

        wiz_id = self.pool.get('signature.add_user.wizard').create(cr, uid, wiz_data, context=context)
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
            'width': '720px',
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
                    for to_remove in ['signature_state', 'signature_user_ids', 'signed_off_line', 'signature_line_ids', 'signature_is_closed']:
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
        self.write(cr, uid, ids, {'signed_off_line': True, 'signature_state': False}, context=context)
        return True


    def activate_offline_reset(self, cr, uid, ids, context=None):
        to_unsign = []
        user_allowed = []
        for doc in self.browse(cr, uid, ids, fields_to_fetch=['signature_line_ids', 'signature_user_ids'], context=context):
            for line in doc.signature_line_ids:
                if line.signed:
                    to_unsign.append(line.id)
            if doc.signature_user_ids:
                user_allowed += [x.id for x in doc.signature_user_ids]

        if to_unsign:
            # disable check if button as BAR (i.e: uid.realUid exists)
            self.pool.get('signature.line').action_unsign(cr, uid, to_unsign, context=context, check_ur=not hasattr(uid, 'realUid'))
        if user_allowed:
            self.pool.get('signature.users.allowed').unlink(cr, uid, user_allowed, context=context)

        return self.activate_offline(cr, uid, ids, context=context)

    def disable_offline(self, cr, uid, ids, context=None):
        _register_log(self, cr, uid, ids, self._name, 'Sign offline', True, False, 'write', context)
        self.write(cr, uid, ids, {'signed_off_line': False}, context=context)
        return True

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        fields_to_reset = [
            'signature_id', 'signature_user_ids', 'signature_line_ids',
            'signature_state', 'signed_off_line', 'signature_is_closed',
            'signature_closed_date', 'signature_closed_user', 'signature_res_id', 'signature_res_model'
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
                ( list_sign.get(self._name) or self._name == 'account.bank.statement' ) and \
                self.pool.get('unifield.setup.configuration').get_config(cr, uid, 'signature') and \
                (   self._name not in ('stock.picking', 'sale.order') or \
                    self._name == 'stock.picking' and vals.get('type') == 'in' or \
                    self._name == 'sale.order' and vals.get('location_requestor_id')
                    ):

            line_obj = self.pool.get('signature.line')
            ftf = ['signature_id']
            if self._name == 'account.bank.statement':
                ftf += ['local_register', 'journal_id']
            elif self._name == 'account.invoice':
                ftf += ['doc_type']

            obj = self.browse(cr, uid, new_id, fields_to_fetch=ftf, context=context)

            if self._name == 'account.bank.statement' and not obj.local_register:
                return new_id

            if self._name == 'account.invoice' and obj.doc_type not in ('si', 'donation'):
                return new_id

            if obj.signature_id:
                if self._name == 'account.bank.statement':
                    key = 'account.bank.statement.%s'%obj.journal_id.type
                else:
                    key = self._name

                for x in list_sign.get(key):
                    line_obj.create(cr, 1, {
                        'name_key': x[0],
                        'name': x[1],
                        'is_active': x[2],
                        'subtype': x[3],
                        'signature_id': obj.signature_id.id
                    }, context=context)
        return new_id

signature_object()

class signature_line(osv.osv):
    _name = 'signature.line'
    _description = 'Document line to sign by role'

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

                key = '%s-%s' % (x.signature_id.signature_res_model, x.doc_state)
                if key not in cache_state:
                    cache_state[key] = self.pool.get('ir.model.fields').get_selection(cr, uid, x.signature_id.signature_res_model, 'state', x.doc_state, context=context)
                res[x.id]['format_state'] = cache_state[key]
        return res

    _columns = {
        'signature_id': fields.many2one('signature', 'Parent', required=1),
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
        'subtype': fields.selection([('full', 'Full Report'), ('rec', 'Reconciliation')], string='Type of signature', readonly=1),
    }

    _defaults = {
        'subtype': '',
    }

    _sql_constraints = [
        ('unique_signature_name_key', 'unique (signature_id,name_key)', 'Unique signature_id,name_key')
    ]
    def _check_sign_unsign(self, cr, uid, ids, check_has_sign=False, context=None):
        assert len(ids) < 2, '_check_sign_unsign: only 1 id is allowed'
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid

        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'subtype'], context=context)
        if (real_uid, sign_line.subtype) not in [(x.user_id.id, x.subtype) for x in sign_line.signature_id.signature_user_ids]:
            raise osv.except_osv(_('Warning'), _("You are not on the list of users allowed to sign this document - please contact the document creator"))

        if sign_line.signature_id.signature_is_closed:
            raise osv.except_osv(_('Warning'), _("Signature Closed."))

        if check_has_sign:
            user_d = self.pool.get('res.users').browse(cr, uid, real_uid, fields_to_fetch=['has_valid_signature', 'esignature_id'], context=context)
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

    def action_unsign(self, cr, uid, ids, context=None, check_ur=True):
        # check_ur: used when sign off line by sign creator
        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'name', 'user_name', 'value', 'unit'], context=context)
        if check_ur:
            sign_line._check_sign_unsign(context=context)

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        value = sign_line.value
        if value is False:
            value = ''
        old = "signed by %s, %s %s" % (sign_line.user_name, value, sign_line.unit)
        desc = 'Delete signature on role %s' % (sign_line.name, )
        _register_log(self, cr, real_uid, sign_line.signature_id.signature_res_id, sign_line.signature_id.signature_res_model, desc, old, '', 'unlink', context)

        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        self.write(cr, root_uid, ids, {'signed': False, 'date': False, 'user_id': False, 'image_id': False, 'value': False, 'unit': False, 'legal_name': False, 'user_name': False, 'doc_state': False}, context=context)
        self.pool.get('signature')._set_signature_state(cr, root_uid, [sign_line.signature_id.id], context=context)
        return True

    def activate_role(self, cr, uid, ids, context=None):
        return self._toggle_active(cr, uid, ids, True, context=context)

    def disable_role(self, cr, uid, ids, context=None):
        return self._toggle_active(cr, uid, ids, False, context=context)

    def _toggle_active(self, cr, uid, ids, value, context=None):
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        for line in self.browse(cr, uid, ids, fields_to_fetch=['is_active', 'signed', 'name', 'signature_id', 'subtype'], context=context):
            if line.is_active == value:
                continue
            if line['signed']:
                raise osv.except_osv(_('Warning'), _("You can't change Active value on an already signed role."))
            txt = 'Signature active on role %s' % (line.name, )
            _register_log(self, cr, real_uid, line.signature_id.signature_res_id, line.signature_id.signature_res_model, txt, '%s'%(not value, ), '%s'%(value, ), 'write', context)

            self.write(cr, uid, line['id'], {'is_active': value}, context=context)

            if not value:
                nb_users = len([x.id for x in line.signature_id.signature_user_ids if x.subtype == line.subtype])
                nb_active = len([x for x in line.signature_id.signature_line_ids if x.is_active and x.subtype == line.subtype]) - 1
                if nb_users > nb_active:
                    raise osv.except_osv(_('Warning'), _('%d users are allowed to sign, you cannot disable this line.') % nb_users)
            self.pool.get('signature')._set_signature_state(cr, root_uid, [line.signature_id.id], context=context)
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
        'user_id': fields.many2one('res.users', required=1, string='User'),
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
    }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        self.pool.get('signature.line').action_sign(cr, uid, [wiz.line_id.id], wiz.value, wiz.unit, wiz.doc_state, context=context)
        return {'type': 'ir.actions.act_window_close', 'o2m_refresh': 'signature_line_ids'}

signature_document_wizard()


class signature_add_user_wizard(osv.osv_memory):
    _name = 'signature.add_user.wizard'
    _description = 'Wizard used on document to add users allowed to sign'

    _columns = {
        'name': fields.char('Document', size=256, readonly=1),
        'signature_id': fields.many2one('signature', readonly=1),
        'res_users': fields.many2many('res.users', string='Signature users', domain=[('signature_enabled', '=', True)]),
        'res_users_rec': fields.many2many('res.users', string='Signature users', domain=[('signature_enabled', '=', True)]),
        'res_users_full': fields.many2many('res.users', string='Signature users', domain=[('signature_enabled', '=', True)]),
        'num_col': fields.integer('Num of profiles', readonly=1),
    }

    _defaults = {
        'num_col': 1,
    }
    def save(self, cr, uid, ids, context=None):
        signature_obj = self.pool.get('signature')

        wiz = self.browse(cr, uid, ids[0], context=context)
        data = {}

        if wiz.num_col == 2:
            wiz_type_users = [('rec', wiz.res_users_rec), ('full', wiz.res_users_full)]
        else:
            wiz_type_users = [('', wiz.res_users)]


        fake_uid = uid
        rules_pool = self.pool.get('msf_button_access_rights.button_access_rule')
        rule_ids = rules_pool.search(cr, 1, [('name', '=', 'add_user_signatures'), ('model_id', '=', wiz.signature_id.signature_res_model)])
        if rule_ids:
            user_group = set(self.pool.get('res.users').read(cr, 1, uid, ['groups_id'])['groups_id'])
            for rule in rules_pool.browse(cr, 1, rule_ids, fields_to_fetch=['group_ids']):
                if user_group.intersection([g.id for g in rule.group_ids]):
                    fake_uid = fakeUid(1, uid)
                    break

        num_listed_users = 0
        for subtype, list_users in wiz_type_users:
            if list_users:
                num_listed_users += len(list_users)
                if wiz.signature_id.signature_line_ids:
                    active_sign = len([x for x in wiz.signature_id.signature_line_ids if x.is_active and x.subtype == subtype])
                else:
                    active_sign = len([x for x in list_sign.get(wiz.signature_id.signature_res_model, []) if x[2] and x[3] == subtype])

                if len(list_users) > active_sign:
                    raise osv.except_osv(_('Warning'), _('A maximum of %d users are allowed to sign') % active_sign)
            else:
                list_users = []
                if wiz.signature_id.signature_state == 'open':
                    data['signature_state'] = False


            for line in wiz.signature_id.signature_line_ids:
                if line.signed and line.subtype == subtype and line.user_id not in list_users:
                    raise osv.except_osv(_('Warning'), _('Document already signed by %s, you cannot remove this user') % (line.user_id.name,))

            to_del = []
            for allowed_obj in wiz.signature_id.signature_user_ids:
                if allowed_obj.subtype == subtype:
                    if allowed_obj.user_id not in list_users:
                        to_del.append((allowed_obj.id, allowed_obj.user_id.name))
                    else:
                        list_users.remove(allowed_obj.user_id)

            for to_create in list_users:
                _register_log(self, cr, uid, wiz.signature_id.signature_res_id, wiz.signature_id.signature_res_model, 'Add User Allowed to sign %s' % (subtype), '', '%s (id:%s)' % (to_create.name, to_create.id) , 'create', context)
                self.pool.get('signature.users.allowed').create(cr, fake_uid, {'signature_id': wiz.signature_id.id, 'user_id': to_create.id, 'subtype': subtype}, context=context)

            for _to_del_id, _to_del_name in to_del:
                _register_log(self, cr, uid, wiz.signature_id.signature_res_id, wiz.signature_id.signature_res_model, 'Delete User Allowed to sign %s' % (subtype), '%s (id:%s)' % (_to_del_name, _to_del_id), '', 'unlink', context)
                self.pool.get('signature.users.allowed').unlink(cr, fake_uid, _to_del_id, context=context)

        previous_state = wiz.signature_id.signature_state
        if num_listed_users and wiz.signature_id.signature_state not in ('partial', 'signed'):
            data['signature_state'] = 'open'
        elif not num_listed_users and wiz.signature_id.signature_state == 'open':
            data['signature_state'] = False

        if data:
            if 'signature_state' in data:
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
            w,h = font.getsize(msg)
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
                    elif obj == 'sale.order':
                        cond = "sale_order o where o.signature_id is not null and o.procurement_request='t'"
                    elif obj.startswith('account.bank.statement'):
                        obj_typ = obj.split('.')[-1]
                        cond = "account_bank_statement o, account_journal j, res_company c where o.journal_id = j.id and o.signature_id is not null and j.type ='%s' and c.instance_id = j.instance_id" % (obj_typ, )
                    elif obj == 'account.invoice':
                        cond = "account_invoice o where o.signature_id is not null and o.real_doc_type in ('donation', 'si') or (o.real_doc_type is null and o.type='in_invoice' and o.is_direct_invoice='f' and o.is_inkind_donation='f' and o.is_debit_note='f' and o.is_intermission='f') or (o.real_doc_type is null and o.type='in_invoice' and o.is_debit_note='f' and o.is_inkind_donation='t')"
                    elif obj == 'stock.picking':
                        cond = "stock_picking o where o.signature_id is not null and o.type='in'"

                    for role in list_sign[obj]:
                        cr.execute("""
                            insert into signature_line (signature_id, is_active, name, name_key, subtype)
                                    select o.signature_id, %%(is_active)s, %%(name)s, %%(name_key)s, %%(subtype)s from
                                    %s
                            on conflict on constraint signature_line_unique_signature_name_key do nothing
                        """ % cond, { # not_a_user_entry
                            'is_active': role[2],
                            'name': role[1],
                            'name_key': role[0],
                            'subtype': role[3],
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
