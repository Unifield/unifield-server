# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import fields, osv
from tools.translate import _
from binascii import unhexlify, hexlify
import simplecrypt
import StringIO
from tools import webdav
import zipfile
from tempfile import NamedTemporaryFile
from urlparse import urlparse

class msf_instance(osv.osv):
    _name = 'msf.instance'

    def _get_current_instance_level(self, cr, uid, ids, fields, arg, context=None):
        if not context:
            context = {}
        res = dict.fromkeys(ids, False)
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id and user.company_id.instance_id:
            for id in ids:
                res[id] = user.company_id.instance_id.level
        return res

    def _get_top_cost_center(self, cr, uid, ids, fields, arg, context=None):
        """
        Search for top cost center from the given instance.
        """
        # Some checks
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Default values
        res = dict.fromkeys(ids, False)
        # Search top cost center
        for instance in self.read(cr, uid, ids, ['target_cost_center_ids', 'level'], context=context):
            target_cc_ids = instance.get('target_cost_center_ids', False)
            if target_cc_ids:
                for target in self.pool.get('account.target.costcenter').read(cr, uid, target_cc_ids, ['is_top_cost_center', 'cost_center_id']):
                    if target.get('is_top_cost_center', False):
                        res[instance.get('id')] = target.get('cost_center_id', [False])[0]
                        break
            elif instance.get('level', '') == 'section':
                parent_cost_centers = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), ('parent_id', '=', '')], context=context)
                if len(parent_cost_centers) > 0:
                    res[instance.get('id')] = parent_cost_centers[0]
        return res

    def _get_po_fo_cost_center(self, cr, uid, ids, fields, arg, context=None):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = dict.fromkeys(ids, False)
        for instance in self.browse(cr, uid, ids, context=context):
            if instance.target_cost_center_ids:
                for target in instance.target_cost_center_ids:
                    if target.is_po_fo_cost_center:
                        res[instance.id] = target.cost_center_id.id
                        break
            elif instance.level == 'section':
                parent_cost_centers = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), ('parent_id', '=', '')], context=context)
                if len(parent_cost_centers) > 0:
                    res[instance.id] = parent_cost_centers[0]
        return res

    def _get_restrict_level_from_entity(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if not ids:
            return res
        for id in ids:
            res[id] = False
        return res

    def _search_restrict_level_from_entity(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        entity = self.pool.get('sync.client.entity')
        if entity:
            entity_obj = entity.get_entity(cr, uid, context=context)
            if not entity_obj:
                return []
            if not entity_obj.parent:
                return [('level', '=', 'section')]
            p_id = self.search(cr, uid, [('instance', '=', entity_obj.parent)])
            if not p_id:
                return []
            return [('parent_id', 'in', p_id)]
        return []

    def _get_instance_child_ids(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        if not ids:
            return res
        for id in ids:
            res[id] = False
        return res

    def _search_instance_child_ids(self, cr, uid, obj, name, args, context=None):
        res = []
        for arg in args:
            if arg[0] == 'instance_child_ids':
                user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
                if user.company_id and user.company_id.instance_id:
                    instance_id = user.company_id.instance_id.id
                    child_ids = self.get_child_ids(cr, uid)
                    # add current instance to display it in the search
                    child_ids.append(instance_id)
                    res.append(('id', 'in', child_ids))
            else:
                res.append(arg)
        return res

    def _search_instance_to_display_ids(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain with:
        - if the current instance is an HQ instance: all instances of all missions
        - if the current instance is a coordo or project instance: all instances with the same mission + the HQ instance
        """
        res = []
        for arg in args:
            if arg[0] == 'instance_to_display_ids':
                user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
                if user.company_id and user.company_id.instance_id and user.company_id.instance_id.level:
                    instance = user.company_id.instance_id
                    # data filtered only for coordo or project
                    if instance.level != 'section' and instance.mission:
                        visible_ids = self.search(cr, uid, [
                            '|',
                            ('mission', '=', instance.mission),
                            ('level', '=', 'section')])
                        res.append(('id', 'in', visible_ids))
            else:
                res.append(arg)
        return res

    _empty_pass = 'X' * 10
    def _get_cloud_set_password(self, cr, uid, ids, fields, arg, context=None):
        ret = {}
        for x in self.read(cr, uid, ids, ['cloud_password'], context=context):
            ret[x['id']] = x['cloud_password'] and self._empty_pass or False
        return ret

    def _set_cloud_password(self, cr, uid, id, name, value, arg, context):
        if not value:
            self.write(cr, uid, id, {'cloud_password': False})
        elif value != self._empty_pass:
            identifier = self.read(cr, uid, id, ['instance_identifier'], context=context)['instance_identifier']
            if not identifier:
                raise osv.except_osv(_('Warning !'), _('Unable to store password if Instance identifier is not set.'))
            cr_password = hexlify(simplecrypt.encrypt(identifier, value))
            self.write(cr, uid, id, {'cloud_password': cr_password}, context=context)
        return True

    def _get_cloud_info(self, cr, uid, id, context=None):
        d = self.read(cr, uid, id, ['instance_identifier', 'cloud_password', 'cloud_url', 'cloud_login'], context=context)
        ret = {
            'url': d['cloud_url'],
            'login': d['cloud_login'],
            'password': False
        }
        if d['cloud_password'] and d['instance_identifier']:
            try:
                ret['password'] = simplecrypt.decrypt(d['instance_identifier'], unhexlify(d['cloud_password']))
            except:
                raise osv.except_osv(_('Warning !'), _('Unable to decode password'))

        return ret

    _columns = {
        'level': fields.selection([('section', 'Section'),
                                   ('coordo', 'Coordo'),
                                   ('project', 'Project')], 'Level', required=True),
        'code': fields.char('Code', size=64, required=True),
        'mission': fields.char('Mission', size=64),
        'instance': fields.char('Instance', size=64),
        #'parent_id': fields.many2one('msf.instance', 'Parent', domain=[('level', '!=', 'project'), ('state', '=', 'active')]),
        'parent_id': fields.many2one('msf.instance', 'Parent', domain=[('level', '!=', 'project')]),
        'child_ids': fields.one2many('msf.instance', 'parent_id', 'Children'),
        'name': fields.char('Name', size=64, required=True),
        'note': fields.char('Note', size=256),
        'target_cost_center_ids': fields.one2many('account.target.costcenter', 'instance_id', 'Target Cost Centers'),
        'state': fields.selection([('draft', 'Draft'),
                                   ('active', 'Active'),
                                   ('inactive', 'Inactive')], 'State', required=True),
        'move_prefix': fields.char('Account move prefix', size=5, required=True),
        'reconcile_prefix': fields.char('Reconcilation prefix', size=5, required=True),
        'current_instance_level': fields.function(_get_current_instance_level, method=True, store=False, string="Current Instance Level", type="char", readonly="True"),
        'top_cost_center_id': fields.function(_get_top_cost_center, method=True, store=False, string="Top cost centre for budget consolidation", type="many2one", relation="account.analytic.account", readonly="True"),
        'po_fo_cost_center_id': fields.function(_get_po_fo_cost_center, method=True, store=False, string="Cost centre picked for PO/FO reference", type="many2one", relation="account.analytic.account", readonly="True"),
        'instance_identifier': fields.char('Instance identifier', size=64, readonly=1),
        'instance_child_ids': fields.function(_get_instance_child_ids, method=True,
                                              string='Proprietary Instance',
                                              type='many2one',
                                              relation='msf.instance',
                                              fnct_search=_search_instance_child_ids),
        'restrict_level_from_entity': fields.function(_get_restrict_level_from_entity, method=True, store=False, fnct_search=_search_restrict_level_from_entity, string='Filter instance from entity info'),
        'instance_to_display_ids': fields.function(_get_instance_child_ids, method=True,
                                                   string='Proprietary Instance',
                                                   type='many2one',
                                                   relation='msf.instance',
                                                   fnct_search=_search_instance_to_display_ids),

        'cloud_url': fields.char('Cloud URL', size=256),
        'cloud_login': fields.char('Cloud Login', size=256),
        'cloud_password': fields.char('Cloud Password', size=256),
        'cloud_schedule_time': fields.float('Schedule task time'),
        'cloud_set_password': fields.function(_get_cloud_set_password, type='char', size=256, fnct_inv=_set_cloud_password, method=True, string='Password'),
    }

    _defaults = {
        'state': 'draft',
        'current_instance_level': 'section',  # UTP-941 set the default value to section, otherwise all fields in the new form are readonly
    }

    def button_cost_center_wizard(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        return {
            'name': "Add Cost Centers",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.add.cost.centers',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'context': context,
        }

    def create(self, cr, uid, vals, context=None):
        # Check if lines are imported from coordo; if now, create those
        res_id = osv.osv.create(self, cr, uid, vals, context=context)
        if 'parent_id' in vals and 'level' in vals and vals['level'] == 'project':
            parent_instance = self.browse(cr, uid, vals['parent_id'], context=context)
            instance = self.browse(cr, uid, res_id, context=context)
            if len(parent_instance.target_cost_center_ids) != len(instance.target_cost_center_ids):
                # delete existing cost center lines
                old_target_line_ids = [x.id for x in instance.target_cost_center_ids]
                self.unlink(cr, uid, old_target_line_ids, context=context)
                # copy existing lines for project
                for line_to_copy in parent_instance.target_cost_center_ids:
                    self.pool.get('account.target.costcenter').create(cr, uid, {'instance_id': instance.id,
                                                                                'cost_center_id': line_to_copy.cost_center_id.id,
                                                                                'is_target': False,
                                                                                'parent_id': line_to_copy.id}, context=context)
        return res_id

    # US-972: Check and show warning message if any costcenter not assigned as target in any instances
    def check_cc_not_target(self, cr, uid, ids, context):
        target_obj = self.pool.get('account.target.costcenter')
        not_target_cc = ''
        for instance in self.browse(cr, uid, ids, context=context):
            for cc in instance.target_cost_center_ids:
                if not target_obj.search(cr, uid, [('cost_center_id', '=', cc.cost_center_id.id), ('is_target', '=', True)]):
                    not_target_cc = not_target_cc + "%s, " % (cc.cost_center_id.name)

        if not_target_cc:
            not_target_cc = not_target_cc[:len(not_target_cc) - 2]
            msg = "Warning: The following cost centers have not been set as target: %s" % not_target_cc
            self.log(cr, uid, ids[0], msg)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 'code' in vals:  # US-972: If the user clicks on Save button, then perform this check
            self.check_cc_not_target(cr, uid, ids, context)
        res = super(msf_instance, self).write(cr, uid, ids, vals, context=context)
        return res

    def _check_name_code_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('|'),
                                            ('name', '=ilike', instance.name),
                                            ('code', '=ilike', instance.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def onchange_parent_id(self, cr, uid, ids, parent_id, level, context=None):
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if parent_id and level == 'project':
            parent_instance = self.browse(cr, uid, parent_id, context=context)
            for instance in self.browse(cr, uid, ids, context=context):
                # delete existing cost center lines
                old_target_line_ids = [x.id for x in instance.target_cost_center_ids]
                self.unlink(cr, uid, old_target_line_ids, context=context)
                # copy existing lines for project
                for line_to_copy in parent_instance.target_cost_center_ids:
                    self.pool.get('account.target.costcenter').create(cr, uid, {'instance_id': instance.id,
                                                                                'cost_center_id': line_to_copy.cost_center_id.id,
                                                                                'is_target': False,
                                                                                'parent_id': line_to_copy.id}, context=context)
        return True

    def _check_database_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('&'),
                                            ('instance', '!=', False),
                                            ('instance', '=', instance.instance)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_move_prefix_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('move_prefix', '=ilike', instance.move_prefix)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_reconcile_prefix_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for instance in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('&'),
                                            ('state', '!=', 'inactive'),
                                            ('reconcile_prefix', '=ilike', instance.reconcile_prefix)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_name_code_unicity, 'You cannot have the same code or name than an active instance!', ['code', 'name']),
        (_check_database_unicity, 'You cannot have the same database than an active instance!', ['instance']),
        (_check_move_prefix_unicity, 'You cannot have the same move prefix than an active instance!', ['move_prefix']),
        (_check_reconcile_prefix_unicity, 'You cannot have the same reconciliation prefix than an active instance!', ['reconcile_prefix']),
    ]

    def get_child_ids(self, cr, uid, instance_ids=None, children_ids_list=None, context=None):
        """
        Search for all the children ids of the instance_ids parameter
        Get the current instance id if no instance_ids is given
        """
        if context is None:
            context = {}
        if instance_ids is None:
            user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            if user.company_id and user.company_id.instance_id:
                instance_ids = [user.company_id.instance_id.id]
        if not instance_ids:
            return []
        current_children = self.search(cr, uid, [('parent_id', 'in',
                                                  tuple(instance_ids))])
        if children_ids_list is None:
            children_ids_list = []
        if not current_children:
            return children_ids_list
        children_ids_list.extend(current_children)
        self.get_child_ids(cr, uid, current_children, children_ids_list,
                           context)
        return children_ids_list

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            txt = rs.code
            res += [(rs.id, txt)]
            context['level'] = rs.level

        return res

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        """
        Search Instance regarding their code and their name
        """
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, uid, [('code', 'ilike', name)] + args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, uid, [('name', 'ilike', name)] + args, limit=limit, context=context)
        return self.name_get(cr, uid, ids, context=context)

    def button_deactivate(self, cr, uid, ids, context=None):
        """
        Deactivate instance
        """
        self.write(cr, uid, ids, {'state': 'inactive'}, context=context)
        return True

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Override the tree view to display historical prices according to context
        '''
        if context is None:
            context = {}
        res = super(msf_instance, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)

        if user.company_id and user.company_id.instance_id:
            current_instance_level = user.company_id.instance_id.current_instance_level

            if current_instance_level != 'section':
                if 'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"' in res['arch']:
                    res['arch'] = res['arch'].replace('hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_duplicate_button="1"')
                    res['arch'] = res['arch'].replace('hide_delete_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_delete_button="1"')
                    res['arch'] = res['arch'].replace('hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', 'hide_new_button="1" noteditable="1" notselectable="0"')

                if 'target_cost_center_ids' in res['fields']:
                    arch = res['fields']['target_cost_center_ids']['views']['tree']['arch']
                    if 'hide_delete_button="PROP_INSTANCE_HIDE_BUTTON' in arch:
                        res['fields']['target_cost_center_ids']['views']['tree']['arch'] = arch.replace('hide_delete_button="PROP_INSTANCE_HIDE_BUTTON', 'noteditable="1" hide_delete_button="1')
            else:
                if res['type'] == 'form' and 'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"' in res['arch']:
                    res['arch'] = res['arch'].replace('hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                    res['arch'] = res['arch'].replace('hide_delete_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                    res['arch'] = res['arch'].replace('hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                if 'target_cost_center_ids' in res['fields']:
                    arch = res['fields']['target_cost_center_ids']['views']['tree']['arch']
                    if 'hide_delete_button="PROP_INSTANCE_HIDE_BUTTON' in arch:
                        res['fields']['target_cost_center_ids']['views']['tree']['arch'] = arch.replace('PROP_INSTANCE_HIDE_BUTTON', '0')

        return res


    def test_connection(self, cr, uid, ids, context=None):
        info = self._get_cloud_info(cr, uid, ids[0])
        if not info.get('url'):
            raise osv.except_osv(_('Warning !'), _('URL is not set!'))
        if not info.get('login'):
            raise osv.except_osv(_('warning !'), _('login is not set!'))
        if not info.get('password'):
            raise osv.except_osv(_('Warning !'), _('Password is not set!'))

        url = urlparse(info['url'])
        if not url.netloc:
            raise osv.except_osv(_('Warning !'), _('Unable to parse url: %s') % (info['url']))

        try:
            dav = webdav.Client(url.netloc, port=url.port, protocol=url.scheme, username=info['login'], password=info['password'], path=url.path, onedrive=True)
        except webdav.ConnectionFailed, e:
            raise osv.except_osv(_('Warning !'), _('Unable to connect: %s') % (e.message))

        test_file_name = 'test-file.txt'
        locale_file = StringIO.StringIO()
        locale_file.write('TEST UF')
        locale_file.seek(0)
        try:
            dav.upload(locale_file, test_file_name)
        except webdav.ConnectionFailed, e:
            raise osv.except_osv(_('Warning !'), _('Unable to upload a test file: %s') % (e.message))

        try:
            dav.delete(test_file_name)
        except webdav.ConnectionFailed, e:
            raise osv.except_osv(_('Warning !'), _('Unable to delete a test file: %s') % (e.message))

        temp_fileobj = NamedTemporaryFile('w+b', delete=True)
        z = zipfile.ZipFile(temp_fileobj, "w")
        z.write('/tmp/OCBPK124-20180205-170411-A-UF7.1.dump', arcname='OCBPK124-20180205-170411-A-UF7.1.dump')
        z.close()
        temp_fileobj.seek(0)
        dav.upload(temp_fileobj, 'OCBPK124.zip')
        temp_fileobj.close()
        print 'OK'
        return True

        """
        #z = zipstream.ZipFile(compression=zipstream.ZIP_DEFLATED, mode='w')
        #z.write('/tmp/SYNC_SERVER.dump', arcname='OCBPK124-20180205-170411-A-UF7.1.dump')
        z = open('/tmp/SYNC_SERVER.dump', 'rb')
        #with open('/tmp/zipfile.zip', 'wb') as f:
        #    for data in z:
        #        f.write(data)
        dav.upload(z, 'OCBPK124.zip')
        print 'OK1'

        z = zipstream.ZipFile(compression=zipstream.ZIP_DEFLATED, mode='w')
        z.write('/tmp/SYNC_SERVER.dump', arcname='OCBPK124-20180205-170411-A-UF7.1.dump')
        dav.upload(z, 'OCBPK124.zip')
        print 'OK2'

        return True
        """

        """
        info = FileCreationInformation()
        info.content = 'Test UF %s' % time.strftime('%Y-%m-%d %H:%M:%S')
        info.url = 'TEST.txt'
        info.overwrite = True
        rel =  web.get_folder_by_server_relative_url('Documents')
        upload_file = rel.files.add(info)
        rel.context.execute_query()

        upload_file.delete_object()
        rel.context.execute_query()
        """

        """
        info = FileCreationInformation()
        f = open('/tmp/OCBPK124-20180205-170411-A-UF7.1.dump', 'rb')
        info.content = f
        info.url = 'OCBPK124-20180205-170411-A-UF7.1.dump'
        rel.files.add(info)
        rel.context.execute_query()
        return True
        """

        """
        ctx_auth = AuthenticationContext(info['url'])
        if ctx_auth.acquire_token_for_user(info['login'], info['password']):
            request = ClientRequest(ctx_auth)
            options = RequestOptions("{0}/_api/web/".format(info['url']))
            options.set_header('Accept', 'application/json')
            options.set_header('Content-Type', 'application/json')
            data = request.execute_query_direct(options)
            print options
            s = json.loads(data.content)
            web_title = s['Title']
            print "Web title: " + web_title
        else:
            print ctx_auth.get_last_error()
            print info
        return True
        """
        """
        webdav = easywebdav.connect(info['url'], username=info['login'], password=info['password'], protocol='https')
        try:
            path = '/'.join(info['url'].split('/')[1:])
            webdav.ls('/')
        except Exception, e:
            raise osv.except_osv(_('Warning !'), _('Unable to list %s: %s' % (path, e)))

        try:
            locale_file = StringIO.StringIO()
            locale_file.write('TEST UF')
            remote_name = 'test-uf-%s' % (time.strftime('%Y-%m-%d-%H%M'), )
            webdav.upload(locale_file, remote_name)
        except Exception, e:
            raise osv.except_osv(_('Warning !'), _('Unable to upload a file %s' % e))
        return True
        """

msf_instance()

class res_users(osv.osv):
    _inherit = 'res.users'
    _name = 'res.users'

    def get_browse_user_instance(self, cr, uid, context=None):
        current_user = self.browse(cr, uid, uid, context=context,
                                   fields_to_fetch=['company_id'])
        return current_user and current_user.company_id and current_user.company_id.instance_id or False
res_users()

class account_bank_statement_line_deleted(osv.osv):
    _inherit = 'account.bank.statement.line.deleted'
    _name = 'account.bank.statement.line.deleted'
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }

account_bank_statement_line_deleted()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
