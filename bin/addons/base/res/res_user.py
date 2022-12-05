# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010-2011 OpenERP s.a. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields,osv
from osv.orm import browse_record
import tools
from functools import partial
import pytz
import pooler
from tools.translate import _
from service import security
import netsvc
import logging
from passlib.hash import bcrypt
from service import http_server
from msf_field_access_rights.osv_override import _get_instance_level
import time
from lxml import etree


class groups(osv.osv):
    _name = "res.groups"
    _order = 'name'
    _description = "Access Groups"

    _columns = {
        'name': fields.char('Group Name', size=64, required=True),
        'model_access': fields.one2many('ir.model.access', 'group_id', 'Access Controls'),
        'rule_groups': fields.many2many('ir.rule', 'rule_group_rel',
                                        'group_id', 'rule_group_id', 'Rules', domain=[('global', '=', False)]),
        'menu_access': fields.many2many('ir.ui.menu', 'ir_ui_menu_group_rel', 'gid', 'menu_id', 'Access Menu', display_inactive=True),
        'comment': fields.text('Comment',size=250),
        'level': fields.selection([('hq', 'HQ'),
                                   ('coordo', 'Coordination'),
                                   ('project', 'Project')],
                                  'Level',
                                  help="Level selected and all higher ones will be able to use this group.",),

        # field defined in module msf_button_access_rights
        #'bar_ids': fields.many2many('msf_button_access_rights.button_access_rule', 'button_access_rule_groups_rel', 'group_id', 'button_access_rule_id', 'Buttons Access Rules', readonly=1),

        # field defined in module msf_field_access_rights
        #'far_ids': fields.many2many('msf_field_access_rights.field_access_rule', 'field_access_rule_groups_rel', 'group_id', 'field_access_rule_id', 'Fields Access Rules', readonly=1),
        'act_window_ids': fields.many2many('ir.actions.act_window', 'ir_act_window_group_rel', 'gid', 'act_id', 'Window Actions', readonly=1),
    }

    _defaults = {
        'level': lambda *a: False,
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name of the group must be unique !')
    ]

    def is_higher_level(self, cr, uid, from_level=None, to_level=None):
        '''
        Return True if from_level is upper level than to_level
        '''

        if from_level is None:
            from_level = _get_instance_level(self, cr, uid)
        if not from_level:
            # SYNC_SERVER doesn't have instance level
            return True
        if not to_level or to_level == 'project':
            return True
        elif from_level == 'hq':
            return True
        elif from_level == 'coordo' and to_level in ('coordo', 'project'):
            return True
        elif from_level == 'project' and to_level == 'project':
            return True
        return False

    def copy(self, cr, uid, id, default=None, context=None):
        group_name = self.read(cr, uid, [id], ['name'])[0]['name']
        default.update({'name': _('%s (copy)')%group_name})
        return super(groups, self).copy(cr, uid, id, default, context)

    def check_level(self, cr, uid, level):
        '''
        Raise an error message if the group level is higher than instance level

        '''
        instance_level = _get_instance_level(self, cr, uid)
        if level and instance_level and not self.is_higher_level(cr, uid, from_level=instance_level, to_level=level):
            selection_dict = dict(self._columns['level'].selection)
            group_level = level and _(selection_dict[level])
            instance_level = instance_level and _(selection_dict[instance_level])
            raise osv.except_osv(_('Error'),
                                 _('You cannot edit a group level higher than your instance level (%s is higher than %s).') % (group_level, instance_level))

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        if 'name' in vals:
            if vals['name'].startswith('-'):
                raise osv.except_osv(_('Error'),
                                     _('The name of the group can not start with "-"'))

        user_obj = self.pool.get('res.users')
        old_users = []
        if 'users' in vals:
            old_users = user_obj.search(cr, uid, [('groups_id', 'in', ids)], context=context)

        bypass_level = context.get('sync_update_execution', False) or context.get('bypass_group_level', False)
        if 'level' in vals and not bypass_level:
            self.check_level(cr, uid, vals['level'])
        elif 'level' in vals and bypass_level:
            # in case of update received with higher group, disassociate the related users
            if vals['level'] and not self.is_higher_level(cr, uid, to_level=vals['level']):
                # remove all users from this groups except uid 1 (admin)
                group_ids_with_admin = []
                group_ids_without_admin = []
                for group in self.read(cr, uid, ids, ['users']):
                    if 1 in group['users']:
                        group_ids_with_admin.append(group['id'])
                    else:
                        group_ids_without_admin.append(group['id'])
                if group_ids_with_admin:
                    self.write(cr, uid, group_ids_with_admin, {'users':[(6, 0, [1])]})
                if group_ids_without_admin:
                    self.write(cr, uid, group_ids_without_admin, {'users':[(6, 0, [])]})

        old_level_dict = {}
        if 'level' in vals:
            # get the old group level
            read_old_level = self.read(cr, uid, ids, ['level'], context=context)
            old_level_dict = dict((x['id'], x['level']) for x in read_old_level)

        res = super(groups, self).write(cr, uid, ids, vals, context=context)

        if 'level' in vals:
            # if the new level is lower level, touch the related users
            user_to_touch_ids = []
            for group_id, group_level in list(old_level_dict.items()):
                if self.is_higher_level(cr, uid,
                                        from_level=group_level,
                                        to_level=vals.get('level', 'project')):  # no level is same as 'project' level
                    users_ids = self.pool.get('res.users').search(cr, uid,
                                                                  [('groups_id', '=', group_id),
                                                                   ('id', '!=', 1),
                                                                   ], context=context)
                    user_to_touch_ids.extend(users_ids)

            if user_to_touch_ids:
                cr.execute('''UPDATE ir_model_data
                              SET touched = '[''groups_id'']', last_modification = now()
                              WHERE model =  'res.users' AND res_id in %s''', (tuple(user_to_touch_ids),))

        self.pool.get('ir.model.access').call_cache_clearing_methods(cr)
        if 'users' in vals:
            new_users = user_obj.search(cr, uid, [('groups_id', 'in', ids)], context=context)
            diff_users = set(old_users).symmetric_difference(new_users)
            if diff_users:
                clear = partial(self.pool.get('ir.rule').clear_cache, cr, old_groups=ids)
                for _user in list(diff_users):
                    clear(_user)
        if 'menu_access' in vals or 'users' in vals:
            self.pool.get('ir.ui.menu')._clean_cache(cr.dbname)
        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if 'name' in vals:
            if vals['name'].startswith('-'):
                raise osv.except_osv(_('Error'),
                                     _('The name of the group can not start with "-"'))
        bypass_level = context.get('sync_update_execution', False) or context.get('bypass_group_level', False)
        if 'level' in vals and not bypass_level:
            self.check_level(cr, uid, vals['level'])

        gid = super(groups, self).create(cr, uid, vals, context=context)
        if context and context.get('noadmin', False):
            pass
        else:
            # assign this new group to user_root
            user_obj = self.pool.get('res.users')
            aid = user_obj.browse(cr, 1, user_obj._get_admin_id(cr))
            if aid:
                aid.write({'groups_id': [(4, gid)]})
        return gid

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        An instance can only view groups of the same level or lower than its own
        '''
        if context is None:
            context = {}

        if 'show_all_level' in context and not context.get('show_all_level'):
            new_args = []
            instance_level = _get_instance_level(self, cr, uid)
            if instance_level == 'project':
                new_args = [('level', 'in', ['project', False])]
            elif instance_level == 'coordo':
                new_args = [('level', 'in', ['project', 'coordo', False])]
            if instance_level in ('project', 'coordo'):
                new_args += [('is_an_admin_profile', '=', False)]
            for arg in args:
                new_args.append(arg)

            args = new_args
        return super(groups, self).search(cr, uid, args, offset=offset,
                                          limit=limit, order=order, context=context, count=count)

    def get_extended_interface_group(self, cr, uid, context=None):
        data_obj = self.pool.get('ir.model.data')
        extended_group_data_id = data_obj._get_id(cr, uid, 'base', 'group_extended')
        return data_obj.browse(cr, uid, extended_group_data_id, context=context).res_id

groups()

def _lang_get(self, cr, uid, context=None):
    obj = self.pool.get('res.lang')
    ids = obj.search(cr, uid, [('translatable','=',True)])
    res = obj.read(cr, uid, ids, ['code', 'name'], context=context)
    res = [(r['code'], r['name']) for r in res]
    return res

def _tz_get(self,cr,uid, context=None):
    return [(x, x) for x in pytz.all_timezones]

class users(osv.osv):
    __admin_ids = {}
    __sync_user_ids = {}
    _uid_cache = {}
    _name = "res.users"
    _order = 'name'
    _trace = True

    WELCOME_MAIL_SUBJECT = "Welcome to OpenERP"
    WELCOME_MAIL_BODY = "An OpenERP account has been created for you, "\
        "\"%(name)s\".\n\nYour login is %(login)s, "\
        "you should ask your supervisor or system administrator if you "\
        "haven't been given your password yet.\n\n"\
        "If you aren't %(name)s, this email reached you errorneously, "\
        "please delete it."

    def get_welcome_mail_subject(self, cr, uid, context=None):
        """ Returns the subject of the mail new users receive (when
        created via the res.config.users wizard), default implementation
        is to return config_users.WELCOME_MAIL_SUBJECT
        """
        return self.WELCOME_MAIL_SUBJECT
    def get_welcome_mail_body(self, cr, uid, context=None):
        """ Returns the subject of the mail new users receive (when
        created via the res.config.users wizard), default implementation
        is to return config_users.WELCOME_MAIL_BODY
        """
        return self.WELCOME_MAIL_BODY

    def get_current_company_partner_id(self, cr, uid):
        company_id = self.get_current_company(cr, uid) and\
            self.get_current_company(cr, uid)[0][0] or False
        if company_id:
            company_obj = self.pool.get('res.company')
            read_result = company_obj.read(cr, uid, company_id,
                                           ['partner_id'])
            return read_result and read_result['partner_id'] or False
        return False

    def get_current_company(self, cr, uid):
        cr.execute('''SELECT company_id, res_company.name
                FROM res_users
                LEFT JOIN res_company ON res_company.id = company_id
                WHERE res_users.id=%s''', (uid,))
        return cr.fetchall()

    def get_company_currency_id(self, cr, uid):
        user = self.browse(cr, uid, uid, fields_to_fetch=['company_id'])
        return user.company_id and user.company_id.currency_id and user.company_id.currency_id.id or False

    def send_welcome_email(self, cr, uid, id, context=None):
        logger= netsvc.Logger()
        user = self.read(cr, uid, id, context=context)
        if not tools.config.get('smtp_server'):
            logger.notifyChannel('mails', netsvc.LOG_WARNING,
                                 _('"smtp_server" needs to be set to send mails to users'))
            return False
        if not tools.config.get('email_from'):
            logger.notifyChannel("mails", netsvc.LOG_WARNING,
                                 _('"email_from" needs to be set to send welcome mails '
                                   'to users'))
            return False
        if not user.get('email'):
            return False

        return tools.email_send(email_from=None, email_to=[user['email']],
                                subject=self.get_welcome_mail_subject(
                                    cr, uid, context=context),
                                body=self.get_welcome_mail_body(
                                    cr, uid, context=context) % user)

    def _email_get(self, cr, uid, ids, name, arg, context=None):
        # perform this as superuser because the current user is allowed to read users, and that includes
        # the email, even without any direct read access on the res_partner_address object.
        return dict([(user.id, user.address_id.email) for user in self.browse(cr, 1, ids)]) # no context to avoid potential security issues as superuser

    def _email_set(self, cr, uid, ids, name, value, arg, context=None):
        if not isinstance(ids,list):
            ids = [ids]
        address_obj = self.pool.get('res.partner.address')
        for user in self.browse(cr, uid, ids, context=context):
            # perform this as superuser because the current user is allowed to write to the user, and that includes
            # the email even without any direct write access on the res_partner_address object.
            if user.address_id:
                address_obj.write(cr, 1, user.address_id.id, {'email': value or None}) # no context to avoid potential security issues as superuser
            else:
                address_id = address_obj.create(cr, 1, {'name': user.name, 'email': value or None}) # no context to avoid potential security issues as superuser
                self.write(cr, uid, ids, {'address_id': address_id}, context)
        return True

    def _set_new_password(self, cr, uid, id, name, value, args, context=None):
        login = self.read(cr, uid, id, ['login'])['login']
        if value is False:
            # Do not update the password if no value is provided, ignore silently.
            # For example web client submits False values for all empty fields.
            return
        if uid == id:
            # To change their own password users must use the client-specific change password wizard,
            # so that the new password is immediately used for further RPC requests, otherwise the user
            # will face unexpected 'Access Denied' exceptions.
            raise osv.except_osv(_('Operation Canceled'), _('Please use the change password wizard (in User Preferences or User menu) to change your own password.'))
        security.check_password_validity(self, cr, uid, None, value, value, login)
        encrypted_password = bcrypt.encrypt(tools.ustr(value))
        self.write(cr, uid, id, {'password': encrypted_password, 'last_password_change': time.strftime('%Y-%m-%d %H:%M:%S')})

    def _is_erp_manager(self, cr, uid, ids, name=None, arg=None, context=None):
        '''
        return True if the user is member of the group_erp_manager (usually,
        admin of the site).
        '''
        if isinstance(ids, int):
            ids = [ids]
        manager_group_id = None
        result = dict.fromkeys(ids, False)
        try:
            dataobj = self.pool.get('ir.model.data')
            dummy, manager_group_id = dataobj.get_object_reference(cr, 1, 'base',
                                                                   'group_erp_manager')
        except ValueError:
            # If these groups does not exists anymore
            pass
        if manager_group_id:
            read_result = self.read(cr, uid, ids, ['groups_id'], context=context)
            for current_user in read_result:
                if manager_group_id in current_user['groups_id']:
                    result[current_user['id']] = True
        return result

    def _search_role(self, cr, uid, obj, name, args, context=None):
        '''
        Return ids matching the condition if research contain is_erp_manager or
        is_sync_config
        '''
        res = []
        for arg in args:
            if len(arg) > 2 and arg[0] == 'is_erp_manager':
                dataobj = self.pool.get('ir.model.data')

                manager_group_id = None
                try:
                    dataobj = self.pool.get('ir.model.data')
                    dummy, manager_group_id = dataobj.get_object_reference(cr, 1, 'base',
                                                                           'group_erp_manager')
                except ValueError:
                    # If these groups does not exists anymore
                    pass
                if manager_group_id:
                    if arg[1] == '=' and arg[2] == False:
                        res.append(('groups_id', 'not in', manager_group_id))
                    if arg[1] == '=' and arg[2] == True:
                        res.append(('groups_id', 'in', manager_group_id))

            elif len(arg) > 2 and arg[0] == 'is_sync_config':
                res_group_obj = self.pool.get('res.groups')
                group_ids = res_group_obj.search(cr, uid,
                                                 [('name', '=', 'Sync_Config')], context=context)
                if group_ids:
                    if arg[1] == '=' and arg[2] == False:
                        res.append(('groups_id', 'not in', group_ids[0]))
                    if arg[1] == '=' and arg[2] == True:
                        res.append(('groups_id', 'in', group_ids[0]))
        return res

    def _is_sync_config(self, cr, uid, ids, name=None, arg=None, context=None):
        '''
        return True if the user is member of the Sync_Config
        '''
        if isinstance(ids, int):
            ids = [ids]
        result = dict.fromkeys(ids, False)
        res_group_obj = self.pool.get('res.groups')
        group_ids = res_group_obj.search(cr, uid,
                                         [('name', '=', 'Sync_Config')], context=context)
        if group_ids:
            group_id = group_ids[0]
            read_result = self.read(cr, uid, ids, ['groups_id'], context=context)
            for current_user in read_result:
                if group_id in current_user['groups_id']:
                    result[current_user['id']] = True
        return result

    def _get_instance_level(self, cr, uid, ids, name=None, arg=None,
                            context=None):
        '''
        return the level of the instance related to the company of the user
        '''
        if isinstance(ids, int):
            ids = [ids]

        level = _get_instance_level(self, cr, uid)
        result = {}.fromkeys(ids, level)
        return result


    def _search_instance_level(self, cr, uid, obj, name, args, context=None):
        res = []
        for arg in args:
            if len(arg) > 2 and arg[0] == 'instance_level':
                level = _get_instance_level(self, cr, uid)
                if arg[1] == '=':
                    if level != arg[2]:
                        res.append(('id', '=', '0'))
                elif arg[1] == '!=':
                    if level == arg[2]:
                        res.append(('id', '=', '0'))
                elif arg[1] == 'in':
                    if level not in arg[2]:
                        res.append(('id', '=', '0'))
        return res

    def _get_has_signature(self, cr, uid, ids, name=None, arg=None, context=None):
        res = {}
        for u in self.browse(cr, uid, ids, fields_to_fetch=['esignature_id', 'signature_from', 'signature_to', 'signature_enabled'], context=context):
            res[u.id] = {'has_signature': False, 'has_valid_signature': False, 'new_signature_required': False}
            if u.esignature_id:
                res[u.id]['has_signature'] = True
                res[u.id]['has_valid_signature'] = True
                if not u.signature_enabled:
                    res[u.id]['has_valid_signature'] = False
                elif u['signature_from'] and fields.date.today() < u['signature_from']:
                    res[u.id]['has_valid_signature'] = False
                elif u['signature_to'] and fields.date.today() > u['signature_to']:
                    res[u.id]['has_valid_signature'] = False
            elif u.signature_enabled and u['signature_from'] and fields.date.today() >= u['signature_from'] and (u['signature_to'] and fields.date.today() <= u['signature_to'] or not u['signature_to']):
                res[u.id]['new_signature_required'] = True
        return res

    _columns = {
        'name': fields.char('User Name', size=64, required=True, select=True,
                            help="The new user's real name, used for searching"
                                 " and most listings"),
        'login': fields.char('Login', size=64, required=True,
                             help="Used to log into the system"),
        'password': fields.char('Password', size=128, invisible=True, help="Keep empty if you don't want the user to be able to connect on the system."),
        'new_password': fields.function(lambda *a:'', method=True, type='char', size=64,
                                        fnct_inv=_set_new_password,
                                        string='Change password', help="Only specify a value if you want to change the user password. "
                                        "This user will have to logout and login again!"),
        'email': fields.char('E-mail', size=64,
                             help='If an email is provided, the user will be sent a message '
                             'welcoming him.\n\nWarning: if "email_from" and "smtp_server"'
                             " aren't configured, it won't be possible to email new "
                             "users."),
        'signature': fields.text('Signature', size=64),
        'address_id': fields.many2one('res.partner.address', 'Address'),

        'signature_enabled': fields.boolean('Enable Signature'),
        'esignature_id': fields.many2one('signature.image', 'Current Signature'),
        'current_signature': fields.related('esignature_id', 'pngb64', string='Signature', type='text', readonly=1),
        'signature_from': fields.date('Signature Start Date'),
        'signature_to': fields.date('Signature End Date'),
        'has_signature': fields.function(_get_has_signature, type='boolean', string='Has Signature', method=1, multi='sign_state'),
        'has_valid_signature': fields.function(_get_has_signature, type='boolean', string='Is Signature Valid', method=1, multi='sign_state'),
        'new_signature_required': fields.function(_get_has_signature, type='boolean', string='Is Signature required', method=1, multi='sign_state'),
        'signature_history_ids': fields.one2many('signature.image', 'user_id', string='De-activated Signatures', readonly=1, domain=[('inactivation_date', '!=', False)]),

        'force_password_change':fields.boolean('Change password on next login',
                                               help="Check out this box to force this user to change his "\
                                               "password on next login."),
        'active': fields.boolean('Active'),
        'action_id': fields.many2one('ir.actions.actions', 'Home Action', help="If specified, this action will be opened at logon for this user, in addition to the standard menu."),
        'menu_id': fields.many2one('ir.actions.actions', 'Menu Action', help="If specified, the action will replace the standard menu for this user."),
        'groups_id': fields.many2many('res.groups', 'res_groups_users_rel', 'uid', 'gid', 'Groups'),

        # Special behavior for this field: res.company.search() will only return the companies
        # available to the current user (should be the user's companies?), when the user_preference
        # context is set.
        'company_id': fields.many2one('res.company', 'Company', required=True,
                                      help="The company this user is currently working for.", context={'user_preference': True}),

        'company_ids':fields.many2many('res.company','res_company_users_rel','user_id','cid','Companies'),
        'context_lang': fields.selection(_lang_get, 'Language', required=True,
                                         help="Sets the language for the user's user interface, when UI "
                                         "translations are available"),
        'context_tz': fields.selection(_tz_get,  'Timezone', size=64,
                                       help="The user's timezone, used to perform timezone conversions "
                                       "between the server and the client."),
        'view': fields.selection([('simple','Simplified'),('extended','Extended')],
                                 string='Interface', help="Choose between the simplified interface and the extended one"),
        'user_email': fields.function(_email_get, method=True, fnct_inv=_email_set, string='Email', type="char", size=240),
        'menu_tips': fields.boolean('Menu Tips', help="Check out this box if you want to always display tips on each menu action"),
        'date': fields.datetime('Last Connection', readonly=True),
        'synchronize': fields.boolean('Synchronize', help="Synchronize down this user", select=1),
        'is_synchronizable': fields.boolean('Is Synchronizable?', help="Can this user be synchronized? The Synchronize checkbox is available only for the synchronizable users.", select=1),
        'is_erp_manager': fields.function(_is_erp_manager, fnct_search=_search_role, method=True, string='Is ERP Manager ?', type="boolean"),
        'is_sync_config': fields.function(_is_sync_config, fnct_search=_search_role, method=True, string='Is Sync Config ?', type="boolean"),
        'instance_level': fields.function(_get_instance_level, fnct_search=_search_instance_level, method=True, string='Instance level', type="char"),
        'log_xmlrpc': fields.boolean('Log XMLRPC requests', help="Log the XMLRPC requests of this user into a dedicated file"),
        'last_use_shortcut': fields.datetime('Last use of shortcut', help="Last date when a shortcut was used", readonly=True),
        'nb_shortcut_used': fields.integer('Number of shortcut used', help="Number of time a shortcut has been used by this user", readonly=True),
        'last_password_change': fields.datetime('Last Password Change', readonly=1),
        'never_expire': fields.boolean('Password never expires', help="If unticked, the password must be changed every 6 months"),
    }

    def fields_get(self, cr, uid, fields=None, context=None, with_uom_rounding=False):
        fg = super(users, self).fields_get(cr, uid, fields, context=context, with_uom_rounding=with_uom_rounding)
        if fg.get('never_expire') and not tools.config.get('is_prod_instance') and not tools.misc.use_prod_sync(cr):
            fg['never_expire']['string'] = '%s (%s)' % (fg['never_expire']['string'], _('not applicable on this sandbox'))
            fg['never_expire']['help'] = _('On this sandbox passwords never expire')

        return fg

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        fvg = super(users, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            signature_enable = self.pool.get('unifield.setup.configuration').get_config(cr, uid, 'signature')
            if not signature_enable:
                arch = etree.fromstring(fvg['arch'])
                fields = arch.xpath('//group[@name="signature_tab"]')
                if fields:
                    parent_node = fields[0].getparent()
                    parent_node.remove(fields[0])
                    fvg['arch'] = etree.tostring(arch, encoding='unicode')
        return fvg

    def on_change_company_id(self, cr, uid, ids, company_id):
        return {
            'warning' : {
                'title': _("Company Switch Warning"),
                'message': _("Please keep in mind that documents currently displayed may not be relevant after switching to another company. If you have unsaved changes, please make sure to save and close all forms before switching to a different company. (You can click on Cancel in the User Preferences now)"),
            }
        }

    def read(self,cr, uid, ids, fields=None, context=None, load='_classic_read'):
        def override_password(o):
            if 'id' not in o or o['id'] != uid:
                o['password'] = '********'
            return o

        result = super(users, self).read(cr, uid, ids, fields, context, load)
        if 'password' in result:
            canwrite = self.pool.get('ir.model.access').check(cr, uid, 'res.users', 'write', raise_exception=False)
            if not canwrite:
                if isinstance(ids, (int, float)):
                    result = override_password(result)
                else:
                    result = list(map(override_password, result))
        return result


    def _check_company(self, cr, uid, ids, context=None):
        return all(((this.company_id in this.company_ids) or not this.company_ids) for this in self.browse(cr, uid, ids, context))

    def _check_signature_group(self, cr, uid, ids, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]

        cr.execute("""
            select u.login from res_users u
                left join res_groups_users_rel rel on rel.uid = u.id
                left join res_groups g on g.id = rel.gid and g.name = 'Sign_user'
            where
                u.id in %s and
                u.signature_enabled = 't'
            group by u.login
            having count(g.name='Sign_user' or null) = 0
        """, (tuple(ids), ))
        wrong = [x[0] for x in cr.fetchall()]
        if wrong:
            raise osv.except_osv(_('Warning'), _('Please add the group Sign_user in order to Enable signatures on user(s) %s') % (', '.join(wrong),))
        return True

    _constraints = [
        (_check_company, 'The chosen company is not in the allowed companies for this user', ['company_id', 'company_ids']),
    ]

    _sql_constraints = [
        ('login_key', 'UNIQUE (login)',  'You can not have two users with the same login !'),
        ('dates_ok', 'CHECK (signature_from<=signature_to)',  'Signature: Start Date must be before End Date !')
    ]

    def _get_email_from(self, cr, uid, ids, context=None):
        if not isinstance(ids, list):
            ids = [ids]
        res = dict.fromkeys(ids, False)
        for user in self.browse(cr, uid, ids, context=context):
            if user.user_email:
                res[user.id] = "%s <%s>" % (user.name, user.user_email)
        return res

    def _get_admin_id(self, cr):
        if self.__admin_ids.get(cr.dbname) is None:
            ir_model_data_obj = self.pool.get('ir.model.data')
            mdid = ir_model_data_obj._get_id(cr, 1, 'base', 'user_root')
            self.__admin_ids[cr.dbname] = ir_model_data_obj.read(cr, 1, [mdid], ['res_id'])[0]['res_id']
        return self.__admin_ids[cr.dbname]

    def _get_sync_user_id(self, cr):
        if self.__sync_user_ids.get(cr.dbname) is None:
            ir_model_data_obj = self.pool.get('ir.model.data')
            mdid = ir_model_data_obj._get_id(cr, 1, 'base', 'user_sync')
            self.__sync_user_ids[cr.dbname] = ir_model_data_obj.read(cr, 1, [mdid], ['res_id'])[0]['res_id']
        return self.__sync_user_ids[cr.dbname]

    def _get_company(self,cr, uid, context=None, uid2=False):
        if not uid2:
            uid2 = uid
        user = self.read(cr, uid, uid2, ['company_id'], context)
        company_id = user.get('company_id', False)
        return company_id and company_id[0] or False

    def _get_companies(self, cr, uid, context=None):
        c = self._get_company(cr, uid, context)
        if c:
            return [c]
        return False

    def _get_menu(self,cr, uid, context=None):
        dataobj = self.pool.get('ir.model.data')
        try:
            model, res_id = dataobj.get_object_reference(cr, uid, 'base', 'action_menu_admin')
            if model != 'ir.actions.act_window':
                return False
            return res_id
        except ValueError:
            return False

    def _get_group(self,cr, uid, context=None):
        dataobj = self.pool.get('ir.model.data')
        result = []
        try:
            dummy,group_id = dataobj.get_object_reference(cr, 1, 'base', 'group_user')
            result.append(group_id)
            dummy,group_id = dataobj.get_object_reference(cr, 1, 'base', 'group_partner_manager')
            result.append(group_id)
        except ValueError:
            # If these groups does not exists anymore
            pass
        return result

    _defaults = {
        'password' : '',
        'context_lang': 'en_US',
        'active' : True,
        'menu_id': _get_menu,
        'company_id': _get_company,
        'company_ids': _get_companies,
        'groups_id': _get_group,
        'address_id': False,
        'menu_tips':True,
        'force_password_change': False,
        'view': 'simple',
        'is_synchronizable': False,
        'synchronize': False,
        'last_password_change': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'never_expire': lambda self, cr, *a: cr.dbname == 'SYNC_SERVER',
    }

    @tools.cache()
    def company_get(self, cr, uid, uid2, context=None):
        return self._get_company(cr, uid, context=context, uid2=uid2)

    # User can write to a few of her own fields (but not her groups for example)
    SELF_WRITEABLE_FIELDS = ['menu_tips','view', 'password', 'signature', 'action_id', 'company_id', 'user_email']

    def remove_higer_level_groups(self, cr, uid, ids, context=None):
        '''
        check the groups of the given user ids and remove those which have
        higher level than the current instance one.
        '''
        if isinstance(ids, int):
            ids = [ids]
        # if the groups change, check all this groups are allowed on this level
        # instance. If not remove the unauthorised ones
        instance_level = _get_instance_level(self, cr, uid)
        if instance_level != 'hq':  # all users and all groups are available on hq
            current_groups = self.read(cr, uid, ids, ['groups_id'],
                                       context=context)
            group_obj = self.pool.get('res.groups')
            for user in current_groups:
                if user['id'] == 1:
                    # do not remove groups from admin
                    continue
                group_ids = user['groups_id']
                if group_ids:
                    # remove the groups that are not visible from this instance level
                    new_group_ids = []
                    for group in group_obj.read(cr, uid, group_ids, ['level'],
                                                context=context):
                        if group_obj.is_higher_level(cr, uid,
                                                     from_level=instance_level, to_level=group['level']):
                            new_group_ids.append(group['id'])

                    if set(group_ids) != set(new_group_ids):
                        # replace the old groups with the authorized ones
                        super(users, self).write(cr, uid, user['id'], {'groups_id':
                                                                       [(6, 0, new_group_ids)]}, context=context)

    def create(self, cr, uid, values, context=None):
        if values.get('login'):
            values['login'] = tools.ustr(values['login']).lower()

        if 'name' not in values:
            values['name'] = values['login']

        user_id = super(users, self).create(cr, uid, values, context)
        if values.get('signature_enabled') or values.get('groups_id'):
            self._check_signature_group(cr, uid, user_id, context=context)

        if 'log_xmlrpc' in values:
            # clear the cache of the list of uid to log
            xmlrpc_uid_cache = http_server.XMLRPCRequestHandler.xmlrpc_uid_cache
            if cr.dbname in xmlrpc_uid_cache:
                xmlrpc_uid_cache[cr.dbname] = None
        if values.get('groups_id'):
            self.remove_higer_level_groups(cr, uid, user_id, context=context)

        return user_id

    def write(self, cr, uid, ids, values, context=None):
        if not ids:
            return True
        if not isinstance(ids, list):
            ids = [ids]
        if ids == [uid]:
            for key in list(values.keys()):
                if not (key in self.SELF_WRITEABLE_FIELDS or key.startswith('context_')):
                    break
            else:
                if 'company_id' in values:
                    if not (values['company_id'] in self.read(cr, 1, uid, ['company_ids'], context=context)['company_ids']):
                        del values['company_id']
                uid = 1 # safe fields only, so we write as super-user to bypass access rights

        if values.get('login'):
            values['login'] = tools.ustr(values['login']).lower()

        old_groups = []
        if values.get('groups_id'):
            old_groups = self.pool.get('res.groups').search(cr, uid, [('users', 'in', ids)], context=context)

        if 'log_xmlrpc' in values:
            # clear the cache of the list of uid to log
            xmlrpc_uid_cache = http_server.XMLRPCRequestHandler.xmlrpc_uid_cache
            if cr.dbname in xmlrpc_uid_cache:
                xmlrpc_uid_cache[cr.dbname] = None

        if values.get('active') is False:
            sign_follow_up = self.pool.get('signature.follow_up')
            open_sign_ids = sign_follow_up.search(cr, uid, [('user_id', 'in', ids), ('signed', '=', 0), ('signature_is_closed', '=', False)], context=context)
            if open_sign_ids:
                list_of_doc = [x.doc_name or '' for x in sign_follow_up.browse(cr, uid, open_sign_ids[0:5], fields_to_fetch=['doc_name'], context=context)]
                if len(open_sign_ids) > 5:
                    list_of_doc.append('...')
                raise osv.except_osv(_('Warning'), _('You can not deactivate this user, %d documents have to be signed\n%s') % (len(open_sign_ids), ', '.join(list_of_doc)))
            for xuser in self.browse(cr, uid, ids, fields_to_fetch=['name', 'has_valid_signature'], context=context):
                if xuser.has_valid_signature:
                    raise osv.except_osv(_('Warning'), _('You can not deactivate %s: the signature is active') % (xuser['name'], ))



        res = super(users, self).write(cr, uid, ids, values, context=context)
        if values.get('signature_enabled') or values.get('groups_id'):
            self._check_signature_group(cr, uid, ids, context=context)

        if values.get('groups_id'):
            self.remove_higer_level_groups(cr, uid, ids, context=context)
            if values.get('synchronize', False) or values.get('is_synchronizable',
                                                              False):
                # uncheck synchronize checkbox if the user is manager
                vals_sync = {
                    'synchronize': False,
                    'is_synchronizable': False,
                }
                erp_manager_res = self._is_erp_manager(cr, uid, ids,
                                                       context=context)
                if any(erp_manager_res.values()):
                    for user_id, is_erp_manager in list(erp_manager_res.items()):
                        if is_erp_manager:
                            super(users, self).write(cr, uid, user_id, vals_sync, context=context)
            self.pool.get('ir.ui.menu')._clean_cache(cr.dbname)

        # clear caches linked to the users
        self.company_get.clear_cache(cr.dbname)
        self.pool.get('ir.model.access').call_cache_clearing_methods(cr)
        clear = partial(self.pool.get('ir.rule').clear_cache, cr, old_groups=old_groups)
        for _id in ids:
            clear(_id)
        db = cr.dbname
        if db in self._uid_cache:
            for id in ids:
                if id in self._uid_cache[db]:
                    del self._uid_cache[db][id]

        return res

    def unlink(self, cr, uid, ids, context=None):
        if 1 in ids:
            raise osv.except_osv(_('Can not remove root user!'), _('You can not remove the admin user as it is used internally for resources created by OpenERP (updates, module installation, ...)'))
        db = cr.dbname
        if db in self._uid_cache:
            for id in ids:
                if id in self._uid_cache[db]:
                    del self._uid_cache[db][id]
        return super(users, self).unlink(cr, uid, ids, context=context)

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args=[]
        if not context:
            context={}
        ids = []
        if name:
            ids = self.search(cr, user, [('login','=',name)]+ args, limit=limit)
        if not ids:
            ids = self.search(cr, user, [('name',operator,name)]+ args, limit=limit)
        return self.name_get(cr, user, ids)

    def copy(self, cr, uid, id, default=None, context=None):
        user2copy = self.read(cr, uid, [id], ['login','name'])[0]
        if default is None:
            default = {}
        copy_pattern = _("%s (copy)")
        copydef = dict(login=(copy_pattern % user2copy['login']),
                       name=(copy_pattern % user2copy['name']),
                       address_id=False, # avoid sharing the address of the copied user!
                       synchronize=False,
                       is_synchronizable=False,
                       signature_enabled=False,
                       esignature_id=False,
                       signature_from=False,
                       signature_to=False,
                       signature_history_ids=False,
                       )
        copydef.update(default)
        return super(users, self).copy(cr, uid, id, copydef, context)

    def context_get(self, cr, uid, context=None):
        user = self.browse(cr, uid, uid, context)
        result = {}
        for k in list(self._columns.keys()):
            if k.startswith('context_'):
                res = getattr(user,k) or False
                if isinstance(res, browse_record):
                    res = res.id
                result[k[8:]] = res or False
        return result

    def action_get(self, cr, uid, context=None):
        dataobj = self.pool.get('ir.model.data')
        data_id = dataobj._get_id(cr, 1, 'base', 'action_res_users_my')
        return dataobj.browse(cr, uid, data_id, context=context).res_id

    def get_user_database_password_from_uid(self, cr, uid):
        '''
        return encrypted password from the database using uid
        '''
        cr.execute("""SELECT password from res_users
                      WHERE id=%s AND active AND (coalesce(is_synchronizable,'f') = 'f' or coalesce(synchronize, 'f') = 'f')""",
                   (uid,))
        res = cr.fetchone()
        if res:
            return tools.ustr(res[0])
        return False

    def get_user_database_password_from_login(self, cr, login):
        '''
        return encrypted password from the database using login
        '''
        login = tools.ustr(login).lower()
        cr.execute("""SELECT password from res_users
                      WHERE login=%s AND active AND (coalesce(is_synchronizable,'f') = 'f' or coalesce(synchronize, 'f') = 'f')""",
                   (login,))
        res = cr.fetchone()
        if res:
            return tools.ustr(res[0])
        return False

    def login(self, db, login, password):
        if not password:
            return False
        login = tools.ustr(login).lower()
        cr = pooler.get_db(db).cursor()
        try:
            database_password = self.get_user_database_password_from_login(cr, login)
            # check the password is a bcrypt encrypted one
            database_password = tools.ustr(database_password)
            password = tools.ustr(password)
            if bcrypt.identify(database_password):
                if not bcrypt.verify(password, database_password):
                    return False
            elif password != database_password:
                return False
            try:
                # autocommit: our single request will be performed atomically.
                # (In this way, there is no opportunity to have two transactions
                # interleaving their cr.execute()..cr.commit() calls and have one
                # of them rolled back due to a concurrent access.)
                # We effectively unconditionally write the res_users line.
                cr.autocommit(True)
                # Even w/ autocommit there's a chance the user row will be locked,
                # in which case we can't delay the login just for the purpose of
                # update the last login date - hence we use FOR UPDATE NOWAIT to
                # try to get the lock - fail-fast
                cr.execute("""SELECT id from res_users
                              WHERE login=%s AND password=%s
                                    AND active FOR UPDATE NOWAIT""",
                           (login, tools.ustr(database_password)), log_exceptions=False)
                cr.execute('UPDATE res_users SET date=now() WHERE login=%s AND password=%s AND active RETURNING id',
                           (login, tools.ustr(database_password)))
            except Exception:
                # Failing to acquire the lock on the res_users row probably means
                # another request is holding it - no big deal, we skip the update
                # for this time, and let the user login anyway.
                logging.getLogger('res.users').warn('Can\'t acquire lock on res users', exc_info=True)
                cr.rollback()
                cr.execute("""SELECT id from res_users
                              WHERE login=%s AND password=%s
                                    AND active""",
                           (login, tools.ustr(database_password)))
            finally:
                res = cr.fetchone()
                if res:
                    return res[0]
        except Exception:
            # Failing to decode password given by the user
            logging.getLogger('res.users').warn('Can\'t decode password given by user at login', exc_info=True)
        finally:
            cr.close()
        return False

    def check(self, db, uid, passwd):
        """Verifies that the given (uid, password) pair is authorized for the database ``db`` and
           raise an exception if it is not."""
        if not passwd:
            # empty passwords disallowed for obvious security reasons
            raise security.ExceptionNoTb('AccessDenied')
        if self._uid_cache.get(db, {}).get(uid) == passwd:
            return
        cr = pooler.get_db(db).cursor()
        try:
            database_password = self.get_user_database_password_from_uid(cr, uid)
            # check the password is a bcrypt encrypted one
            database_password = tools.ustr(database_password)
            passwd = tools.ustr(passwd)
            if bcrypt.identify(database_password):
                if not bcrypt.verify(passwd, database_password):
                    raise security.ExceptionNoTb('AccessDenied')
            elif passwd != database_password:
                raise security.ExceptionNoTb('AccessDenied')

            if db in self._uid_cache:
                ulist = self._uid_cache[db]
                ulist[uid] = passwd
            else:
                self._uid_cache[db] = {uid:passwd}
        finally:
            cr.close()

    def access(self, db, uid, passwd, sec_level, ids):
        if not passwd:
            return False
        cr = pooler.get_db(db).cursor()
        try:
            cr.execute('SELECT id FROM res_users WHERE id=%s AND password=%s', (uid, passwd))
            res = cr.fetchone()
            if not res:
                raise security.ExceptionNoTb('Bad username or password')
            return res[0]
        finally:
            cr.close()

    def pref_change_password(self, cr, uid, old_passwd, new_passwd,
                             confirm_passwd, context=None):
        self.check(cr.dbname, uid, tools.ustr(old_passwd))
        login = self.read(cr, uid, uid, ['login'])['login']
        return self.change_password(cr.dbname, login, old_passwd, new_passwd,
                                    confirm_passwd, context=context)

    def change_password(self, db_name, login, old_passwd, new_passwd,
                        confirm_passwd, context=None):
        """Change current user password. Old password must be provided explicitly
        to prevent hijacking an existing user session, or for cases where the cleartext
        password is not used to authenticate requests.

        The write of the new password is done with uid=1 to prevent raise if
        the current logged user don't have permission on res_users.

        :return: True
        :raise: security.ExceptionNoTb when old password is wrong
        :raise: except_osv when new password is not set or empty
        """
        if new_passwd:
            cr = pooler.get_db(db_name).cursor()
            try:
                login = tools.ustr(login).lower()
                # get user_uid
                cr.execute("""SELECT id from res_users
                              WHERE login=%s AND active=%s AND (coalesce(is_synchronizable,'f') = 'f' or coalesce(synchronize, 'f') = 'f')""",
                           (login, True))
                res = cr.fetchone()
                uid = None
                if res:
                    uid = res[0]
                if not uid:
                    raise security.ExceptionNoTb('AccessDenied')
                security.check_password_validity(self, cr, uid, old_passwd, new_passwd, confirm_passwd, login)
                new_passwd = bcrypt.encrypt(tools.ustr(new_passwd))
                vals = {
                    'password': new_passwd,
                    'force_password_change': False,
                    'last_password_change': time.strftime('%Y-%m-%d %H:%M:%S'),
                }
                self.check(db_name, uid, tools.ustr(old_passwd))
                result = self.write(cr, 1, uid, vals)
                cr.commit()
            finally:
                cr.close()
            return result
        raise osv.except_osv(_('Warning!'), _("Setting empty passwords is not allowed for security reasons!"))

    def get_admin_profile(self, cr, uid, context=None):
        return uid == 1

    def _archive_signature(self, cr, uid, ids, new_from=None, new_to=None, context=None):
        sign_line_obj = self.pool.get('signature.line')
        for user in self.browse(cr, uid, ids, fields_to_fetch=['esignature_id', 'signature_from', 'signature_to', 'name'] , context=context):
            if user.esignature_id:
                data = {
                    'from_date': user.signature_from,
                    'to_date': user.signature_to or fields.date.today(),
                    'inactivation_date': fields.datetime.now(),
                }
                if user.esignature_id.user_name != user.name:
                    used_sign_id = sign_line_obj.search(cr, uid, [('image_id','=', user.esignature_id.id)], order='id desc', limit=1, context=context)
                    if used_sign_id:
                        last_sign = sign_line_obj.read(cr, uid, used_sign_id[0], ['user_name'], context=context)
                        data['user_name'] = last_sign['user_name']

                self.pool.get('signature.image').write(cr, uid, user.esignature_id.id, data, context=context)
            new_data = {
                'esignature_id': False,
            }
            if new_from is not None:
                new_data['signature_from'] = new_from
                if user.signature_to and new_from >= user.signature_to:
                    new_data['signature_to'] = False
            self.write(cr, uid, [user.id], new_data, context=context)
        return True

    def delete_signature(self, cr, uid, ids, context=None):
        return self._archive_signature(cr, uid, ids, context=context)

    def reset_signature(self, cr, uid, ids, context=None):
        return self._archive_signature(cr, uid, ids, new_from=fields.date.today(), context=context)

    def add_signature(self, cr, uid, ids, context=None):
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        if real_uid != ids[0]:
            raise osv.except_osv(_('Warning!'), _("You can only change your own signature."))
        wiz_id = self.pool.get('signature.set_user').create(cr, uid, {'user_id': real_uid}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'signature.set_user',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
        }

    def replace_signature(self, cr, uid, ids, context=None):
        return self.add_signature(cr, uid, ids, context=context)

    def change_date(self, cr, uid, ids, context=None):
        user = self.pool.get('res.users').browse(cr, uid, ids[0], context=context)
        wiz_id = self.pool.get('signature.change_date').create(cr, uid, {'user_id': ids[0], 'current_from': user.signature_from, 'current_to': user.signature_to}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'signature.change_date',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '250px',
            'width': '720px',
        }

    def change_signature_enabled(self, cr, uid, ids, sign, groups, context=None):
        ret = {}
        if sign:
            ret['value'] = {'signature_from': fields.date.today()}
        return ret

    def open_my_signature(self, cr, uid, context=None):
        user_data =  self.browse(cr, uid, uid, fields_to_fetch=['new_signature_required', 'has_valid_signature'], context=context)
        if not user_data.new_signature_required and not user_data.has_valid_signature:
            raise osv.except_osv(_('Warning'), _('Signature is not enabled on your profile'))

        return {
            'res_id': uid,
            'res_model': 'res.users',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'useability_dashboard_and_menu', 'res_users_my_signature_form')[1]],
            'domain': [('id', '=', uid)],
        }
users()

class wizard_add_users_synchronized(osv.osv_memory):
    _name = 'wizard.add.users.synchronized'

    _columns = {
        'user_ids': fields.many2many('res.users', 'res_add_users_synchronized_rel', 'gid', 'uid', 'Users'),
    }


    def add_users_to_white_list(self, cr, uid, ids, context=None):
        '''
        Set users as synchronizable
        '''
        context = context is None and {} or context
        ids = isinstance(ids, int) and [ids] or ids
        user_obj = self.pool.get('res.users')
        for wiz in self.read(cr, uid, ids, ['user_ids'], context=context):
            user_obj.write(cr, uid, wiz['user_ids'], {'is_synchronizable': True}, context=context)
        return {'type': 'ir.actions.act_window_close'}

wizard_add_users_synchronized()

class config_users(osv.osv_memory):
    _name = 'res.config.users'
    _inherit = ['res.users', 'res.config']

    def _generate_signature(self, cr, name, email, context=None):
        return _('--\n%(name)s %(email)s\n') % {
            'name': name or '',
            'email': email and ' <'+email+'>' or '',
        }

    def create_user(self, cr, uid, new_id, context=None):
        """ create a new res.user instance from the data stored
        in the current res.config.users.

        If an email address was filled in for the user, sends a mail
        composed of the return values of ``get_welcome_mail_subject``
        and ``get_welcome_mail_body`` (which should be unicode values),
        with the user's data %-formatted into the mail body
        """
        base_data = self.read(cr, uid, new_id, context=context)
        partner_id = self.pool.get('res.partner').main_partner(cr, uid)
        address = self.pool.get('res.partner.address').create(
            cr, uid, {'name': base_data['name'],
                      'email': base_data['email'],
                      'partner_id': partner_id,},
            context)
        user_data = dict(
            base_data,
            signature=self._generate_signature(
                cr, base_data['name'], base_data['email'], context=context),
            address_id=address,
        )
        new_user = self.pool.get('res.users').create(
            cr, uid, user_data, context)
        self.send_welcome_email(cr, uid, new_user, context=context)
    def execute(self, cr, uid, ids, context=None):
        'Do nothing on execution, just launch the next action/todo'
        pass
    def action_add(self, cr, uid, ids, context=None):
        'Create a user, and re-display the view'
        self.create_user(cr, uid, ids[0], context=context)
        return {
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'res.config.users',
            'view_id':self.pool.get('ir.ui.view')\
            .search(cr,uid,[('name','=','res.config.users.confirm.form')]),
            'type': 'ir.actions.act_window',
            'target':'new',
        }
config_users()

class groups2(osv.osv): ##FIXME: Is there a reason to inherit this object ?
    _inherit = 'res.groups'
    _columns = {
        'users': fields.many2many('res.users', 'res_groups_users_rel', 'gid', 'uid', 'Users'),
    }

    def _track_change_of_users(self, cr, uid, previous_values, user_ids,
                               vals, context=None):
        '''add audittrail entry to the related users if their groups were changed
        @param previous_values: list of dict containing groups_ids of the users
        @param user_ids: related user ids
        @param vals: vals parameter from the write/create
        '''
        current_values = {}
        audit_obj = self.pool.get('audittrail.rule')
        if context is None:
            context = {}
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        if 'users' in vals:
            if vals['users'] and len(vals['users'][0]) > 2:
                users_deleted = list(set(user_ids).difference(vals['users'][0][2]))
                users_added = list(set(vals['users'][0][2]).difference(user_ids))
                user_obj = self.pool.get('res.users')
                if not hasattr(user_obj, 'check_audit'):
                    return
                audit_rule_ids = user_obj.check_audit(cr, uid, 'write')
                if users_deleted:
                    users_deleted_previous_values = [x for x in previous_values if x['id'] in users_deleted]
                    current_values = dict((x['id'], x) for x in user_obj.read(cr, uid, users_deleted, ['groups_id'], context=context))
                    audit_obj.audit_log(cr, uid, audit_rule_ids, user_obj,
                                        users_deleted, 'write',
                                        users_deleted_previous_values,
                                        current_values,
                                        context=context)
                if users_added:
                    users_added_previous_values = [x for x in previous_values if x['id'] in users_added]
                    current_values = dict((x['id'], x) for x in user_obj.read(cr, uid, users_added, ['groups_id'], context=context))
                    audit_obj.audit_log(cr, uid, audit_rule_ids, user_obj,
                                        users_added, 'write',
                                        users_added_previous_values,
                                        current_values,
                                        context=context)

    def create(self, cr, uid, vals, context=None):
        '''
        In case user have been added, a new audit line should be created on the related users
        '''
        change_user_group = False
        previous_values = []
        if context is None:
            context = {}
        if 'users' in vals and vals['users'] and len(vals['users'][0]) > 2:
            user_obj = self.pool.get('res.users')
            previous_values = user_obj.read(cr, uid, vals['users'][0][2], ['groups_id'], context=context)
            if previous_values:
                change_user_group = True
        group_id = super(groups2, self).create(cr, uid, vals, context=context)
        if change_user_group:
            self._track_change_of_users(cr, uid, previous_values, [],
                                        vals, context=context)
        return group_id

    def write(self, cr, uid, ids, vals, context=None):
        '''
        In case user have been added or deleted, a new audit line should be created on the related users
        '''
        all_user_ids = [] # previous user ids + current
        previous_values = []
        previous_user_ids = []
        removed_user_ids = []
        is_sign_group = False
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if 'users' in vals:
            new_user_ids = []
            if vals['users'] and len(vals['users'][0]) > 2:
                new_user_ids = vals['users'][0][2]
            for record in self.read(cr, uid, ids, ['users', 'name'], context=context):
                if record['name'] == 'Sign_user':
                    is_sign_group = True
                if record['users']:
                    previous_user_ids.extend(record['users'])
            all_user_ids = set(new_user_ids).union(previous_user_ids)
            removed_user_ids = set(previous_user_ids) - set(new_user_ids)
            user_obj = self.pool.get('res.users')
            previous_values = user_obj.read(cr, uid, all_user_ids, ['groups_id'], context=context)

        res = super(groups2, self).write(cr, uid, ids, vals, context=context)
        if 'users' in vals:
            self._track_change_of_users(cr, uid, previous_values, previous_user_ids,
                                        vals, context=context)
        if is_sign_group and removed_user_ids:
            self.pool.get('res.users')._check_signature_group(cr, uid, list(removed_user_ids), context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        group_users = []
        for record in self.read(cr, uid, ids, ['users'], context=context):
            if record['users']:
                group_users.extend(record['users'])

        if group_users:
            user_names = [user.name for user in self.pool.get('res.users').browse(cr, uid, group_users, context=context)]
            if len(user_names) >= 5:
                user_names = user_names[:5]
                user_names += '...'
            raise osv.except_osv(_('Warning !'),
                                 _('Group(s) cannot be deleted, because some user(s) still belong to them: %s !') % \
                                 ', '.join(user_names))
        return super(groups2, self).unlink(cr, uid, ids, context=context)

groups2()

class res_config_view(osv.osv_memory):
    _name = 'res.config.view'
    _inherit = 'res.config'
    _columns = {
        'name':fields.char('Name', size=64),
        'view': fields.selection([('simple','Simplified'),
                                  ('extended','Extended')],
                                 'Interface', required=False ),
    }
    _defaults={
        'view': 'simple',
    }

    def execute(self, cr, uid, ids, context=None):
        res = self.read(cr, uid, ids)[0]
        self.pool.get('res.users').write(cr, uid, [uid],
                                         {'view':res['view']}, context=context)

res_config_view()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
