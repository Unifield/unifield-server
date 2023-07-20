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
from tools import misc
from tools import config
import os
import StringIO
from tools import webdav
import zipfile
from tempfile import NamedTemporaryFile
from urlparse import urlparse
from mx import DateTime
import logging
import requests
import time
import threading
import pooler

class msf_instance(osv.osv):
    _name = 'msf.instance'
    _trace = True

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

    def _get_has_journal_entries(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}

        res = {}
        for _id in ids:
            res[_id] = False

        cr.execute("select id from msf_instance i where i.id in %s and exists(select instance_id from account_move where instance_id=i.id)", (tuple(ids), ))
        for q in cr.fetchall():
            res[q[0]] = True
        return res

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
        'has_journal_entries': fields.function(_get_has_journal_entries, method=True, type='boolean', string='Has Journal Entries'),

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
        if 'state' not in vals:
            # state by default at creation time = Draft: add it in vals to make it appear in the Track Changes
            vals['state'] = 'draft'
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

    def button_activate(self, cr, uid, ids, context=None):
        """
        (Re)activate the instances
        """
        return self.write(cr, uid, ids, {'state': 'active'}, context=context)

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


msf_instance()

class msf_instance_cloud(osv.osv):
    # split cloud config from msf.instance objet to not disturb msf.instance sync
    _inherit = 'msf.instance'
    _table = 'msf_instance'
    _name = 'msf.instance.cloud'

    _logger = logging.getLogger('cloud.backup')
    _empty_pass = 'X' * 10
    _temp_folder = 'Temp'

    _backoff_max = 5
    _backoff_factor = 0.1

    def _get_backoff(self, dav, error):
        if not dav:
            self._logger.info(error)
            time.sleep(self._backoff_factor)

        nb_errors = dav.session_nb_error
        dav.session_nb_error += 1
        if nb_errors <= 1:
            return 0

        if nb_errors % 5 == 0:
            self._logger.info(error)

        backoff_value = self._backoff_factor * (2 ** (nb_errors - 1))
        sleep_time = min(self._backoff_max, backoff_value)
        time.sleep(sleep_time)


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
            crypt_o = misc.crypt(identifier)
            self.write(cr, uid, id, {'cloud_password': crypt_o.encrypt(value)}, context=context)
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
                crypt_o = misc.crypt(d['instance_identifier'])
                ret['password'] = crypt_o.decrypt(d['cloud_password'])
            except:
                raise osv.except_osv(_('Warning !'), _('Unable to decode password'))

        return ret

    def _get_is_editable(self, cr, uid, ids, fields, arg, context=None):
        ret = {}

        # editable at HQ only
        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if not local_instance or local_instance.level != 'section':
            for id in ids:
                ret[id] = False
            return ret

        for instance in self.read(cr, uid, ids, ['instance_identifier'], context=context):
            ret[instance['id']] = bool(instance['instance_identifier'])
        return ret

    def _get_has_config(self, cr, uid, ids, fields, arg, context=None):
        ret = {}
        fields = ['instance_identifier', 'cloud_url', 'cloud_login', 'cloud_password']
        for instance in self.read(cr, uid, ids, fields, context=context):
            ret[instance['id']] = True
            for field in fields:
                if not instance[field]:
                    ret[instance['id']] = False
                    break
        return ret

    def _search_has_config(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []

        if args[0][1] != '=':
            raise osv.except_osv(_('Error'), _('Filter not implemented'))

        if args[0][2]:
            return  [('instance_identifier', '!=', False), ('cloud_url', '!=', False), ('cloud_login', '!=', False), ('cloud_password', '!=', False)]

        return ['|', '|', '|', ('instance_identifier', '=', False), ('cloud_url', '=', False), ('cloud_login', '=', False), ('cloud_password', '=', False)]

    def _get_filter_by_level(self, cr, uid, ids, fields, arg, context=None):
        ret = {}
        for id in ids:
            ret[id] = False
        return ret

    def _search_filter_by_level(self, cr, uid, ids, fields, arg, context=None):
        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if not local_instance or local_instance.level != 'section':
            return [('id', '=', local_instance and local_instance.id or 0)]

        return []

    def copy_to_all(self, cr, uid, ids, context=None):
        info = self._get_cloud_info(cr, uid, ids[0], context=context)
        sc_info = self.read(cr, uid, ids[0], ['delay_minute', 'cloud_schedule_time', 'cloud_retry_from', 'cloud_retry_to'])
        to_write = self.search(cr, uid, [('instance_identifier', '!=', False), ('filter_by_level', '=', True), ('id', '!=', ids[0])], context=context)
        init_time = sc_info['cloud_schedule_time'] or 0
        retry_from = sc_info['cloud_retry_from'] or 0
        retry_to =  sc_info['cloud_retry_to'] or 0
        for x in to_write:
            data = {'cloud_url': info['url'] , 'cloud_login': info['login'], 'cloud_set_password':  info['password'], 'cloud_retry_from': retry_from, 'cloud_retry_to': retry_to, 'delay_minute': -1}
            if sc_info['delay_minute'] and sc_info['delay_minute'] != -1:
                init_time += (sc_info['delay_minute'] or 0) / 60.
                init_time = init_time % 24
                data['cloud_schedule_time'] = init_time

            self.write(cr, uid, x, data, context=context)

        return True

    _columns = {
        'cloud_url': fields.char('Cloud URL', size=256),
        'cloud_login': fields.char('Cloud Login', size=256),
        'cloud_password': fields.char('Cloud Password', size=1024),
        'cloud_schedule_time': fields.float('Schedule task time', help="Remote time"),
        'cloud_set_password': fields.function(_get_cloud_set_password, type='char', size=256, fnct_inv=_set_cloud_password, method=True, string='Password'),
        'cloud_retry_from': fields.float('Retry from time'),
        'cloud_retry_to': fields.float('Retry to time'),
        'is_editable': fields.function(_get_is_editable, type='boolean', string='Has identifier', method=True),
        'has_config': fields.function(_get_has_config, string='Is configured', method=True, type='boolean', fnct_search=_search_has_config),
        'filter_by_level': fields.function(_get_filter_by_level, string='Filter Instance', method=True, type='boolean', internal=True, fnct_search=_search_filter_by_level),
        'delay_minute': fields.integer('Delay (in minutes) to add on schedule time', help="Set '-1' to leave Schedule task time untouched"),
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('sync_update_execution'):
            if not vals.get('instance'):
                raise osv.except_osv(_('Warning !'), 'Instance not set in update')
            instance_ids = self.pool.get('msf.instance').search(cr, uid, [('instance', '=', vals['instance'])], context=context)
            if not instance_ids:
                raise osv.except_osv(_('Warning !'), 'Instance %s not found' % (vals['instance'], ))
            super(msf_instance_cloud, self).write(cr, uid, instance_ids[0], vals, context)
            return instance_ids[0]

        return super(msf_instance_cloud, self).create(cr, uid, vals, context)

    def get_backup_connection_data(self, cr, uid, ids, context=None):
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
        return {
            'host': url.netloc,
            'port': url.port,
            'protocol': url.scheme,
            'username': info['login'],
            'password': info['password'],
            'path': url.path,
        }

    def get_backup_connection(self, cr, uid, ids, context=None):
        data = self.get_backup_connection_data(cr, uid, ids, context=context)
        try:
            dav = webdav.Client(**data)
        except webdav.ConnectionFailed, e:
            raise osv.except_osv(_('Warning !'), _('Unable to connect: %s') % (e.message))

        return dav

    def test_connection(self, cr, uid, ids, context=None):
        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        dav = self.get_backup_connection(cr, uid, ids, context=None)
        test_file_name = 'test-file-%s.txt' % (local_instance.instance, )
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

        try:
            dav.create_folder(self._temp_folder)
        except webdav.ConnectionFailed, e:
            raise osv.except_osv(_('Warning !'), _('Unable to create temp folder: %s') % (e.message))

        raise osv.except_osv(_('OK'), _('Connection to remote storage is OK'))

        return True

    def _activate_cron(self, cr, uid, ids, context=None):
        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if local_instance and local_instance.id in ids:
            fields = ['cloud_url', 'cloud_login', 'cloud_password', 'instance_identifier']
            myself = self.read(cr, uid, local_instance.id, fields+['cloud_schedule_time'], context=context)
            to_activate = True
            for field in fields:
                if not myself[field]:
                    to_activate = False
                    break

            cron_data = self.pool.get('ir.model.data').get_object(cr, uid, 'msf_instance', 'ir_cron_remote_backup')
            to_write = {}
            if not to_activate and cron_data.active:
                to_write['active'] = False
            elif to_activate:
                if not cron_data.active:
                    if self.pool.get('backup.config').search(cr, uid, [('backup_type', '=', 'sharepoint')]):
                        to_write['active'] = True

                next_cron = DateTime.strptime(cron_data.nextcall, '%Y-%m-%d %H:%M:%S')
                if not cron_data.active or abs(round(next_cron.hour + next_cron.minute/60.,2) - round(myself['cloud_schedule_time'],2)) > 0.001:
                    next_time = DateTime.now()  + DateTime.RelativeDateTime(minute=0, second=0, hour=round(myself['cloud_schedule_time'],3)) + DateTime.RelativeDateTime(seconds=0)
                    if next_time < DateTime.now():
                        next_time += DateTime.RelativeDateTime(days=1)
                    to_write['nextcall'] = next_time.strftime('%Y-%m-%d %H:%M:00')
            if to_write:
                self._logger.info('Update scheduled task to send backup: active: %s, next call: %s (previous active: %s, next: %s)' % (to_write.get('active', ''), to_write.get('nextcall', ''), cron_data.active, cron_data.nextcall))
                self.pool.get('ir.cron').write(cr, uid, [cron_data.id], to_write, context=context)

        return True

    def _is_in_time_range(self, starttime, endtime):
        if starttime == endtime:
            return False
        start_dt = (DateTime.now()+DateTime.RelativeDateTime(hour=starttime or 0,minute=0, second=0)).time
        end_dt = (DateTime.now()+DateTime.RelativeDateTime(hour=endtime or 0,minute=0, second=0)).time
        now_dt = DateTime.now().time

        if start_dt < end_dt:
            return now_dt >= start_dt and now_dt <= end_dt

        return now_dt >= start_dt or now_dt <= end_dt

    def send_backup_bg(self, cr, uid, progress=False, context=None):
        if not self.pool.get('backup.config').search(cr, uid, [('backup_type', '=', 'sharepoint')]):
            self._logger.warn('SharePoint push: the cron task is active but the backup configuration is set to Cont. Backup')
            return True
        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if not local_instance:
            return True
        info = self._get_cloud_info(cr, uid, local_instance.id)
        for data in ['url', 'login', 'password']:
            if not info[data]:
                self.pool.get('sync.version.instance.monitor').create(cr, uid, {'cloud_error': 'SharePoint indentifiers not set.'}, context=context)
                return True
        thread = threading.Thread(target=self.send_backup_run, args=(cr.dbname, uid, progress, context))
        thread.start()
        return True

    def send_backup_run(self, dbname, uid, progress=False, context=None):
        new_cr = pooler.get_db(dbname).cursor()
        try:
            self.send_backup(new_cr, uid, progress=progress, context=context)
        except:
            new_cr.rollback()
            raise
        finally:
            new_cr.commit()
            new_cr.close(True)

    def send_backup(self, cr, uid, progress=False, context=None):
        day_abr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        monitor = self.pool.get('sync.version.instance.monitor')
        bck_download = self.pool.get('backup.download')

        local_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        monitor_ids = monitor.search(cr, uid, [('instance_id', '=', local_instance.id)], context=context)
        param_obj = self.pool.get('ir.config_parameter')
        buffer_size = param_obj.get_param(cr, 1, 'CLOUD_BUFFER_SIZE')
        if not buffer_size:
            buffer_size = 10 * 1024 * 1024
            param_obj.set_param(cr, 1, 'CLOUD_BUFFER_SIZE',  buffer_size)
            cr.commit()
        buffer_size = int(buffer_size)
        progress_obj = False

        try:
            if not config.get('send_to_onedrive') and not misc.use_prod_sync(cr, uid, self.pool):
                raise osv.except_osv(_('Warning'), _('Only production instances are allowed !'))

            if not local_instance:
                msg = _('No instance defined on company')
                self._logger.info(msg)
                raise osv.except_osv(_('Warning'), msg)


            bck_download.populate(cr, 1, context=context)
            # Only my dump
            bck_ids = bck_download.search(cr, uid, [('name', 'like', '%s%%' % local_instance.instance)], limit=1)
            if not bck_ids:
                msg = _('No dump found')
                self._logger.info(msg)
                raise osv.except_osv(_('Warning'), msg)

            bck = bck_download.read(cr, uid, bck_ids[0], ['path', 'name'])

            if monitor_ids:
                previous_backup = monitor.read(cr, uid, monitor_ids[0], ['cloud_backup'])['cloud_backup']
                if previous_backup == bck['name']:
                    raise osv.except_osv(_('Warning'), _('Backup %s was already sent to the cloud') % (bck['name'], ))

            dav_data = self.get_backup_connection_data(cr, uid, [local_instance.id], context=None)

            range_data = self.read(cr, uid, local_instance.id, ['cloud_retry_from', 'cloud_retry_to'], context=context)
            temp_fileobj = NamedTemporaryFile('w+b', delete=True)
            z = zipfile.ZipFile(temp_fileobj, "w", compression=zipfile.ZIP_DEFLATED)
            z.write(bck['path'], arcname=bck['name'])
            z.close()
            temp_fileobj.seek(0)

            zip_size = os.path.getsize(temp_fileobj.name)
            today = DateTime.now()

            self._logger.info('OneDrive: upload backup started, buffer_size: %s, total size %s' % (misc.human_size(buffer_size), misc.human_size(zip_size)))
            if progress:
                progress_obj = self.pool.get('msf.instance.cloud.progress').browse(cr, uid, progress)

            final_name = '%s-%s.zip' % (local_instance.instance, day_abr[today.day_of_week])
            temp_drive_file = '%s/%s.zip' % (self._temp_folder, local_instance.instance)

            dav_connected = False
            temp_create = False
            error = False
            upload_ok = False
            dav = False
            while True:
                try:
                    if not dav_connected:
                        dav = webdav.Client(**dav_data)
                        dav_connected = True

                    if not temp_create:
                        dav.create_folder(self._temp_folder)
                        temp_create = True

                    if not upload_ok:
                        upload_ok, error = dav.upload(temp_fileobj, temp_drive_file, buffer_size=buffer_size, log=True, progress_obj=progress_obj, continuation=True)

                    # please don't change the following to else:
                    if upload_ok:
                        dav.move(temp_drive_file, final_name)
                        break
                    else:
                        if not self._is_in_time_range(range_data['cloud_retry_from'], range_data['cloud_retry_to']):
                            break

                        self._get_backoff(dav, 'OneDrive: retry %s' % error)
                        if 'timed out' in error or '2130575252' in error:
                            self._logger.info('OneDrive: session time out')
                            dav.login()

                except requests.exceptions.RequestException, e:
                    if not self._is_in_time_range(range_data['cloud_retry_from'], range_data['cloud_retry_to']):
                        raise
                    self._get_backoff(dav, 'OneDrive: retry except %s' % e)

            if not upload_ok:
                if error:
                    raise Exception(error)
                else:
                    raise Exception('Unknown error')
            temp_fileobj.close()
            monitor.create(cr, uid, {'cloud_date': today.strftime('%Y-%m-%d %H:%M:%S'), 'cloud_backup': bck['name'], 'cloud_error': '', 'cloud_size': zip_size})
            if progress_obj:
                progress_obj.write({'state': 'Done', 'name': 100, 'message': _('Backup successfully sent!')})
            self._logger.info('OneDrive: upload backup ended')
            return True

        except Exception, e:
            cr.rollback()
            if monitor_ids:
                monitor.write(cr, uid, monitor_ids, {'cloud_error': '%s'%e})
                cr.commit()
            if isinstance(e, osv.except_osv):
                error = e.value
            else:
                error = e
            self._logger.error('OneDrive: unable to upload backup %s' % misc.ustr(error))
            if progress_obj:
                progress_obj.write({'state': 'Done', 'message': _("Error during upload:\n%s") % (misc.ustr(error))})
            raise


    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        d = self.pool.get('msf.instance').get_sd_ref(cr, uid, res_id)
        return d.replace('/msf_instance/', '/msf_instance_cloud/')

    _constraints = [
        (_activate_cron, 'Sync cron task', []),
    ]

msf_instance_cloud()


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
