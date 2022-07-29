# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.translate import _
from tools.misc import fakeUid
from lxml import etree


list_sign = {
    'purchase.order': [
        # (key, label, active, subtyp)
        ('sr', _('Supply Responsible'), True, ''),
        ('tr', _('Technical Responsible'), True, ''),
        ('fr', _('Finance Responsible'), True, ''),
        ('mr', _('Mission Responsible'), False, ''),
        ('hq', _('HQ'), False, False),
    ],
    'sale.order': [
        ('tr', _('Technical Responsible'), True, ''),
        ('sr', _('Supply Responsible'), True, ''),
    ],
    'account.bank.statement': [
        ('fr', _('Finance Responsible - reconciliation'), True, 'rec'),
        ('mr', _('Mission Responsible - reconciliation'), True, 'rec'),
        ('fr_report', _('Finance Responsible - full report'), True, 'full'),
        ('mr_report', _('Mission Responsible - full report'), True, 'full'),
    ],
    'account.invoice': [
        ('fr', _('Finance Responsible - reconciliation'), True, ''),
        ('mr', _('Mission Responsible - reconciliation'), True, ''),
    ],
    'stock.picking': [
        ('tr', _('Technical Responsible'), True, ''),
        ('sr', _('Supply Responsible'), True, ''),
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
    'account.bank.statement': lambda doc: doc.journal_id.type == 'bank' and round(doc.balance_end, 2) or doc.journal_id.type == 'cash' and round(doc.msf_calculated_balance, 2) or 0,
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


    _columns = {
        'signature_user_ids': fields.one2many('signature.users.allowed', 'signature_id', 'Users allowed to sign'),
        'signature_line_ids': fields.one2many('signature.line', 'signature_id', 'Lines'),
        'signature_res_model': fields.char('Model', size=254, index=1),
        'signature_res_id': fields.integer('Id', index=1),
        'signature_state': fields.selection([('open', 'Open'), ('partial', 'Partially Signed'), ('signed', 'Fully Signed')], string='Signature State', readonly=True),
        'signed_off_line': fields.boolean('Signed Off Line'),
        'signature_is_closed': fields.boolean('Signature Closed', readonly=True),
        'signature_available': fields.boolean('Activate Signature'),
        'signature_closed_date': fields.datetime('Date of signature closure', readonly=1),
        'signature_closed_user': fields.many2one('res.users', 'Closed by', readonly=1),
    }

    _sql_constraints = [
        ('unique_signature_res_id_model,', 'unique(signature_res_id, signature_res_model)', 'Signature must be unique'),
    ]

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

        self.write(cr, uid, ids, {'signature_state': signature_state}, context=context)
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
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        self.write(cr, uid, ids, {
            'signature_is_closed': True,
            'signature_closed_date': fields.datetime.now(),
            'signature_closed_user': real_uid,
        }, context=context)
        return True


    def sig_line_change(self, cr, uid, ids, context=None):
        states = dict(self._inherit_fields['signature_state'][2].selection)
        translated_states = dict([(k, _(v)) for k, v in states.items()])

        doc = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_state'], context=context)
        return {'value': {'signature_state': doc.signature_state}, 'display_strings': {'signature_state': translated_states}}

    def add_user_signatures(self, cr, uid, ids, context=None):
        doc_name = self.name_get(cr, uid, ids, context=context)[0][1]
        doc = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'signature_res_model'], context=context)


        wiz_data = {
            'name': doc_name,
            'signature_id': doc.signature_id.id,
            'res_users_rec': [(6, 0, [])],
            'res_users_full': [(6, 0, [])],
        }
        if doc.signature_res_model == 'account.bank.statement':
            for user in doc.signature_id.signature_user_ids:
                if user.subtype == 'rec':
                    wiz_data['res_users_rec'][0][2].append(user.user_id.id)
                else:
                    wiz_data['res_users_full'][0][2].append(user.user_id.id)
            view_id = [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'signature_add_user_register_wizard_form')[1]]
        else:
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
                    parent_node = fields[0].getparent()
                    parent_node.remove(fields[0])
                    fvg['arch'] = etree.tostring(arch)
        return fvg

    def activate_signature(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'signature_available': True}, context=context)
        return True

    def disable_signature(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'signature_available': False}, context=context)
        return True

    def activate_offline(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'signed_off_line': True}, context=context)
        return True

    def disable_offline(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'signed_off_line': False}, context=context)
        return True

signature_object()

class signature_line(osv.osv):
    _name = 'signature.line'
    _description = 'Document line to sign by role'

    def _format_value(self, cr, uid, ids, name=None, arg=None, context=None):
        res = {}
        user_lang = self.pool.get('res.users').read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
        lang_obj = self.pool.get('res.lang')
        lang_id = lang_obj.search(cr, uid, [('code', '=', user_lang)])[0]
        for x in self.browse(cr, uid, ids, fields_to_fetch=['signed', 'value', 'unit'], context=context):
            if not x.signed:
                res[x.id] = False
            elif x.value is not False:
                res[x.id] = '%s %s' % (lang_obj.format(cr, uid, [lang_id], '%.2lf', x.value, grouping=True, monetary=True),  x.unit)
            else:
                res[x.id] = x.unit
        return res

    _columns = {
        'signature_id': fields.many2one('signature', 'Parent', required=1),
        'user_id': fields.many2one('res.users', 'Signee User'),
        'legal_name': fields.char('Legal name', size=64),
        'is_active': fields.boolean('Active'),
        'name': fields.char('Role/Function', size=128),
        'name_key': fields.char('key', size=10),
        'signed': fields.boolean('Signed'),
        'image_id': fields.many2one('signature.image', 'Image'),
        'image': fields.related('image_id', 'pngb64', type='text', string='Signature', readonly=1),
        'data_image': fields.related('image_id', 'image', type='text', string='Signature', readonly=1),
        'date': fields.datetime('Date'),
        'value': fields.float_null('Value', digits=(16,2)),
        'unit': fields.char('Unit', size=16),
        'format_value': fields.function(_format_value, method=1, type='char', string='Value'),
        'subtype': fields.selection([('full', 'Full Report'), ('rec', 'Reconciliation')], string='Type of signature', readonly=1),
    }

    _defaults = {
        'subtype': '',
    }

    def _check_sign_unsign(self, cr, uid, ids, check_has_sign=False, context=None):
        assert len(ids) < 2, '_check_sign_unsign: only 1 id is allowed'
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid

        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'subtype'], context=context)
        if (real_uid, sign_line.subtype) not in [(x.user_id.id, x.subtype) for x in sign_line.signature_id.signature_user_ids]:
            raise osv.except_osv(_('Warning'), _("Operation denied"))

        if sign_line.signature_id.signature_is_closed:
            raise osv.except_osv(_('Warning'), _("Signature Closed."))

        if check_has_sign:
            user_d = self.pool.get('res.users').browse(cr, uid, real_uid, fields_to_fetch=['has_valid_signature', 'esignature_id'], context=context)
            if not user_d.has_valid_signature:
                raise osv.except_osv(_('Warning'), _("No signature defined in user's profile"))
            return user_d.esignature_id.id

        return True

    def open_sign_wizard(self, cr, uid, ids, context=None):
        esignature_id = self._check_sign_unsign(cr, uid, ids, check_has_sign=True, context=context)
        line = self.browse(cr, uid, ids[0], context=context)
        doc = self.pool.get(line.signature_id.signature_res_model).browse(cr, uid, line.signature_id.signature_res_id, context=context)

        image = self.pool.get('signature.image').browse(cr, uid, esignature_id, context=context).pngb64

        unit = saved_unit[line.signature_id.signature_res_model](doc)
        value = saved_value[line.signature_id.signature_res_model](doc)
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

    def _register_log(self, cr, uid, res_id, res_model, desc, old, new, log_type, context=None):
        audit_line_obj = self.pool.get('audittrail.log.line')
        audit_rule_obj = self.pool.get('audittrail.rule')

        model_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', res_model)], context=context)[0]

        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        return audit_line_obj.create(cr, root_uid, {
            'description': desc,
            'name': desc,
            'log': audit_rule_obj.get_sequence(cr, uid, res_model, res_id, context=context),
            'object_id': model_id,
            'user_id': uid,
            'method': log_type,
            'res_id': res_id,
            'new_value': new,
            'new_value_text': new,
            'old_value': old,
            'old_value_text': old,
            'field_description': desc,
        }, context=context)

    def action_sign(self, cr, uid, ids, value, unit, context=None):

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'name'], context=context)
        esignature_id = sign_line._check_sign_unsign(check_has_sign=True, context=context)
        user = self.pool.get('res.users').browse(cr, uid, real_uid, fields_to_fetch=['name'], context=context)

        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        self.write(cr, root_uid, ids, {'signed': True, 'date': fields.datetime.now(), 'user_id': real_uid, 'image_id': esignature_id, 'value': value, 'unit': unit, 'legal_name': user.name}, context=context)

        if value is False:
            value = ''
        new = "signed by %s, %s %s" % (user.name, value, unit)
        desc = "Signature added on role %s" % (sign_line.name, )
        self._register_log(cr, real_uid, sign_line.signature_id.signature_res_id, sign_line.signature_id.signature_res_model, desc, '', new, 'create', context)
        self.pool.get('signature')._set_signature_state(cr, root_uid, [sign_line.signature_id.id], context=context)
        return True

    def action_unsign(self, cr, uid, ids, context=None):
        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id', 'name', 'legal_name', 'value', 'unit'], context=context)
        sign_line._check_sign_unsign(context=context)

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        value = sign_line.value
        if value is False:
            value = ''
        old = "signed by %s, %s %s" % (sign_line.legal_name, value, sign_line.unit)
        desc = 'Delete signature on role %s' % (sign_line.name, )
        self._register_log(cr, real_uid, sign_line.signature_id.signature_res_id, sign_line.signature_id.signature_res_model, desc, old, '', 'unlink', context)

        root_uid = hasattr(uid, 'realUid') and uid or fakeUid(1, uid)
        self.write(cr, root_uid, ids, {'signed': False, 'date': False, 'user_id': False, 'image_id': False, 'value': False, 'unit': False, 'legal_name': False}, context=context)
        self.pool.get('signature')._set_signature_state(cr, root_uid, [sign_line.signature_id.id], context=context)
        return True

    def toggle_active(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, fields_to_fetch=['is_active', 'signed', 'name', 'signature_id', 'subtype'], context=context):
            if line['signed']:
                raise osv.except_osv(_('Warning'), _("You can't change Active value on an already signed role."))
            txt = 'Signature active on role %s' % (line.name, )
            real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
            self._register_log(cr, real_uid, line.signature_id.signature_res_id, line.signature_id.signature_res_model, txt, '%s'%line.is_active, '%s'%(not line.is_active,), 'write', context)

            self.write(cr, uid, line['id'], {'is_active': not line['is_active']}, context=context)

            if line['is_active']:
                nb_users = len([x.id for x in line.signature_id.signature_user_ids if x.subtype == line.subtype])
                nb_active = len([x for x in line.signature_id.signature_line_ids if x.is_active and x.subtype == line.subtype]) - 1
                if nb_users > nb_active:
                    raise osv.except_osv(_('Warning'), _('%d users are allowed to sign, you cannot disable this line.') % nb_users)
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
        for img in self.browse(cr, uid, ids, fields_to_fetch=['legal_name'], context=context):
            ret.append((img.id, '%s (id:%s)' % (img.legal_name, img.id)))

        return ret

    _columns = {
        'user_id': fields.many2one('res.users', required=1, string='User'),
        'legal_name': fields.char('Legal name', size=64),
        'image': fields.text('Signature'),
        'pngb64': fields.function(_get_image, method=1, type='text', string='Image'),
        'from_date': fields.date('From Date', readonly=True),
        'to_date': fields.date('To Date', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),
        'inactivation_date': fields.datetime('Inactivation Date', readonly=True),
    }

signature_image()

class signature_document_wizard(osv.osv_memory):
    _name = 'signature.document.wizard'
    _description = 'Wizard used to sign a document'
    _columns = {
        'name': fields.char('Document', size=256, readonly=1),
        'user_id': fields.many2one('Users', readonly=1),
        'role': fields.char('Role/Function', size=256, readonly=1),
        'line_id': fields.many2one('signature.line', 'Line', readonly=1),
        'image': fields.text('Signature', readonly=1),
        'value': fields.float('Value', digits=(16, 2)),
        'unit': fields.char('Unit', size=16),
    }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        self.pool.get('signature.line').action_sign(cr, uid, [wiz.line_id.id], wiz.value, wiz.unit, context=context)
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
    }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        data = {}

        if wiz.signature_id.signature_res_model == 'account.bank.statement':
            wiz_type_users = [('rec', wiz.res_users_rec), ('full', wiz.res_users_full)]
        else:
            wiz_type_users = [('', wiz.res_users)]

        num_listed_users = 0
        for subtype, users in wiz_type_users:
            list_users = [x.id for x in users]
            if users:
                num_listed_users += len(list_users)
                active_sign = len([x for x in list_sign.get(wiz.signature_id.signature_res_model, []) if x[2] and x[3] == subtype])

                if len(list_users) > active_sign:
                    raise osv.except_osv(_('Warning'), _('A maximum of %d users are allowed to sign') % active_sign)
            else:
                list_users = []
                if wiz.signature_id.signature_state == 'open':
                    data['signature_state'] = False


            for line in wiz.signature_id.signature_line_ids:
                if line.signed and line.subtype == subtype and line.user_id.id not in list_users:
                    raise osv.except_osv(_('Warning'), _('Document already signed by %s, you cannot remove this user') % (line.user_id.name,))

            to_del = []
            for allowed_obj in wiz.signature_id.signature_user_ids:
                if allowed_obj.subtype == subtype:
                    if allowed_obj.user_id.id not in list_users:
                        to_del.append(allowed_obj.id)
                    else:
                        list_users.remove(allowed_obj.user_id.id)

            for to_create in list_users:
                self.pool.get('signature.users.allowed').create(cr, uid, {'signature_id': wiz.signature_id.id, 'user_id': to_create, 'subtype': subtype}, context=context)

            if to_del:
                self.pool.get('signature.users.allowed').unlink(cr, uid, to_del, context=context)

        if num_listed_users and wiz.signature_id.signature_state not in ('partial', 'signed'):
            data['signature_state'] = 'open'
        elif not num_listed_users and wiz.signature_id.signature_state == 'open':
            data['signature_state'] = False
        if data:
            wiz.signature_id.write(data, context=context)


        # create missing lines to be signed
        existing_keys = [(x.name_key, x.subtype) for x in wiz.signature_id.signature_line_ids]
        if list_sign.get(wiz.signature_id.signature_res_model, []):
            wiz.signature_id.write({'signature_line_ids': [(0, 0, {'name_key': x[0], 'name': x[1] , 'is_active': x[2], 'subtype': x[3]}) for x in list_sign.get(wiz.signature_id.signature_res_model) if (x[0], x[3]) not in existing_keys]}, context=context)

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
        'new_signature': fields.text('New signature'),
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'preview': fields.boolean('Preview'),
    }

    _defaults = {
        'preview': False,
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
            new_image = self.pool.get('signature.image').create(cr, root_uid, {
                'user_id': real_uid,
                'image': wiz.new_signature,
                'legal_name': wiz.user_id.name,
                'from_date': wiz.user_id.signature_from,
                'to_date': wiz.user_id.signature_to,
            }, context=context)
            self.pool.get('res.users').write(cr, root_uid, real_uid, {'esignature_id': new_image}, context=context)

        return {'type': 'closepref'}

signature_set_user()


class signature_change_date(osv.osv_memory):
    _name = 'signature.change_date'
    _rec_name = 'user_id'
    _description = "Change Dates on user's signature"

    _columns = {
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'current_from': fields.date('Current Date From', readonly=1),
        'current_to': fields.date('Current Date To', readonly=1),
        'new_to': fields.date('New Date To', required=1),
    }

    def change_new_to(self, cr, uid, ids, current_from, new_to, context=None):
        if new_to < current_from:
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _('New Date To can not be before Date From')
                }
            }
        return {}

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        if wiz.new_to < wiz.current_from:
            raise osv.except_osv(_('Warning'), _('Date To can not be before Date From'))

        self.pool.get('res.users').write(cr, uid, wiz.user_id.id, {'signature_to': wiz.new_to}, context=context)
        self.pool.get('signature.image').write(cr, uid, wiz.user_id.esignature_id.id, {'to_date': wiz.new_to}, context=context)

        return {'type': 'ir.actions.act_window_close'}

signature_change_date()

class signature_setup(osv.osv_memory):
    _name = 'signature.setup'
    _inherit = 'res.config'

    _columns = {
        'signature': fields.boolean(string='Activate Elecronique Validation ?'),
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
                if self.pool.get('signature.image').search_exists(cr, uid, [], context=context):
                    raise osv.except_osv(_('Warning'), _('Signature Already Created, you cannot disable this feature !'))
            for module, xmlid in [('useability_dashboard_and_menu', 'signature_follow_up_menu'), ('base', 'signature_image_menu')]:
                menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, xmlid)[1]
                self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': wiz.signature}, context=context)
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
