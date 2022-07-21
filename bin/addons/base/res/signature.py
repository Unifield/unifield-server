# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.translate import _


list_sign = {
    'purchase.order': [
        # (key, label, active)
        ('sr', _('Supply Responsible'), True),
        ('tr', _('Technical Responsible'), True),
        ('fr', _('Finance Responsible'), True),
        ('mr', _('Mission Responsible'), False),
        ('hq', _('HQ'), False),
    ],
}

class signature(osv.osv):
    _name = 'signature'
    _rec_name = 'signature_users'
    _description = 'List of signatures'
    _record_source = True

    _columns = {
        'signature_users': fields.many2many('res.users', 'user_signature_rel', 'signature_id', 'user_id', 'Users allowed to sign'),
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
        doc = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id'], context=context)
        wiz_id = self.pool.get('signature.add_user.wizard').create(cr, uid, {
            'name': doc_name,
            'signature_id': doc.signature_id.id,
            'res_users': [(6, 0, [x.id for x in doc.signature_id.signature_users])],
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'signature.add_user.wizard',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
        }

signature_object()

class signature_line(osv.osv):
    _name = 'signature.line'
    _description = 'Document Signature'


    _columns = {
        'signature_id': fields.many2one('signature', 'Parent', required=1),
        'user_id': fields.many2one('res.users', 'Signee User'),
        'is_active': fields.boolean('Active'),
        'name': fields.char('Role/Function', size=128),
        'name_key': fields.char('key', size=10),
        'signed': fields.boolean('Signed'),
        'image_id': fields.many2one('signature.image', 'Image'),
        'image': fields.related('image_id', 'pngb64', type='text', string='Signature', readonly=1),
        'data_image': fields.related('image_id', 'image', type='text', string='Signature', readonly=1),
        'date': fields.datetime('Date'),
    }


    def _check_sign_unsign(self, cr, uid, ids, check_has_sign=False, context=None):
        assert len(ids) < 2, '_check_sign_unsign: only 1 id is allowed'
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid

        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id'], context=context)
        if real_uid not in [x.id for x in sign_line.signature_id.signature_users]:
            raise osv.except_osv(_('Warning'), _("Operation denied"))

        if sign_line.signature_id.signature_is_closed:
            raise osv.except_osv(_('Warning'), _("Signature Closed."))

        if check_has_sign:
            user_d = self.pool.get('res.users').browse(cr, uid, real_uid, fields_to_fetch=['esignature_id'], context=context)
            if not user_d.esignature_id:
                raise osv.except_osv(_('Warning'), _("No signature defined in user's profile"))
            return user_d.esignature_id.id

        return True

    def open_sign_wizard(self, cr, uid, ids, context=None):
        esignature_id = self._check_sign_unsign(cr, uid, ids, check_has_sign=True, context=context)
        line = self.browse(cr, uid, ids[0], context=context)
        doc = self.pool.get(line.signature_id.signature_res_model).browse(cr, uid, line.signature_id.signature_res_id, fields_to_fetch=['name', 'functional_amount_total', 'functional_currency_id'], context=context)

        image = self.pool.get('signature.image').browse(cr, uid, esignature_id, context=context).pngb64

        wiz_id = self.pool.get('signature.document.wizard').create(cr, uid, {
            'name': '%s %s %s' % (doc.name, doc.functional_amount_total, doc.functional_currency_id.name),
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

    def action_sign(self, cr, uid, ids, context=None):

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id'], context=context)
        esignature_id = sign_line._check_sign_unsign(check_has_sign=True, context=context)

        self.write(cr, uid, ids, {'signed': True, 'date': fields.datetime.now(), 'user_id': real_uid, 'image_id': esignature_id}, context=context)
        sign_line.signature_id._set_signature_state(context=context)

        return True

    def action_unsign(self, cr, uid, ids, context=None):
        sign_line = self.browse(cr, uid, ids[0], fields_to_fetch=['signature_id'], context=context)
        sign_line._check_sign_unsign(context=context)

        self.write(cr, uid, ids, {'signed': False, 'date': False, 'user_id': False, 'image_id': False}, context=context)
        sign_line.signature_id._set_signature_state(context=context)
        return True

signature_line()

class signature_image(osv.osv):
    _name = 'signature.image'
    _description = 'Image'
    _rec_name = 'user_id'

    def _get_image(self, cr, uid, ids, name=None, arg=None, context=None):
        res = {}
        for u in self.browse(cr, uid, ids, fields_to_fetch=['image'], context=context):
            if u.image:
                res[u.id] = u.image.split(',')[-1]
            else:
                res[u.id] = False
        return res

    _columns = {
        'user_id': fields.many2one('res.users', required=1, string='User'),
        'image': fields.text('Signature'),
        'pngb64': fields.function(_get_image, method=1, type='text', string='Image'),
    }

signature_image()

class signature_document_wizard(osv.osv_memory):
    _name = 'signature.document.wizard'
    _columns = {
        'name': fields.char('Document', size=256, readonly=1),
        'user_id': fields.many2one('Users', readonly=1),
        'role': fields.char('Role/Function', size=256, readonly=1),
        'line_id': fields.many2one('signature.line', 'Line', readonly=1),
        'image': fields.text('Signature', readonly=1),
    }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        self.pool.get('signature.line').action_sign(cr, uid, [wiz.line_id.id], context=context)
        return {'type': 'ir.actions.act_window_close'}

signature_document_wizard()


class signature_add_user_wizard(osv.osv_memory):
    _name = 'signature.add_user.wizard'
    _columns = {
        'name': fields.char('Document', size=256, readonly=1),
        'signature_id': fields.many2one('signature', readonly=1),
        'res_users': fields.many2many('res.users', string='Signature users'),
    }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        if wiz.res_users:
            data = {'signature_users': [(6, 0,  [x.id for x in wiz.res_users])]}
            active_sign = len([x for x in list_sign.get(wiz.signature_id.signature_res_model, []) if x[2]])

            if len([x.id for x in wiz.res_users]) > active_sign:
                raise osv.except_osv(_('Warning'), _('A maximum of %d users are allowed to sign') % active_sign)

            if wiz.signature_id.signature_state not in ('partial', 'signed'):
                data['signature_state'] = 'open'
        else:
            data = {'signature_users': [(6, 0, [])]}
            if wiz.signature_id.signature_state == 'open':
                data['signature_state'] = False

        wiz.signature_id.write(data, context=context)


        existing_keys = [x.name_key for x in wiz.signature_id.signature_line_ids]

        if list_sign.get(wiz.signature_id.signature_res_model, []):
            wiz.signature_id.write({'signature_line_ids': [(0, 0, {'name_key': x[0], 'name': x[1] , 'is_active': x[2]}) for x in list_sign.get(wiz.signature_id.signature_res_model) if x[0] not in existing_keys]}, context=context)

        return {'type': 'ir.actions.act_window_close'}
signature_add_user_wizard()

class signature_set_user(osv.osv_memory):
    _name = 'signature.set_user'
    _description = "Wizard to edit user's signature"
    _rec_name = 'user_id'

    _columns = {
        'new_signature': fields.text('New signature'),
        'user_id': fields.many2one('res.users', 'User', readonly=1),
    }

    def save(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        if wiz.new_signature:
            new_image = self.pool.get('signature.image').create(cr, real_uid, {
                'user_id': real_uid,
                'image': wiz.new_signature
            }, context=context)
            self.pool.get('res.users').write(cr, real_uid, real_uid, {'esignature_id': new_image}, context=context)

        return {'type': 'ir.actions.act_window_close'}

signature_set_user()
