#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Max Mumford
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

from osv import osv, orm
import pooler
import logging
from tools.misc import fakeUid

super_view_look_dom_arch = orm.orm_template._orm_template__view_look_dom_arch

def view_look_dom_arch(self, cr, uid, node, view_id, context=None):
    """
    Dynamically change button groups based on button access rules
    """

    if context is None:
        context = {}

    if uid != 1:

        rules_pool = self.pool.get('msf_button_access_rights.button_access_rule')

        # view_id == 0 if view generated on fly by openerp because no custom view specified, therefore we will have no rules
        if view_id:
            search_ids = rules_pool.get_family_ids(cr, uid, view_id)
        else:
            return super_view_look_dom_arch(self, cr, uid, node, view_id, context)

        rules_search = rules_pool.search(cr, 1, [('view_id', 'in', search_ids)])

        # if have rules
        if rules_search:
            rules = rules_pool.browse(cr, 1, rules_search, context=context)

            # parse view and get all buttons with a name, a type that is not 'special', no position attribute, and may or may not have an invisible attribute (But not set to '1')
            buttons = node.xpath("//button[ @name and @type != 'special' and not (@position) and @invisible != '1' and @invisible != 'True' or not (@invisible) ]")
            for button in buttons:

                button_name = button.attrib.get('name', '')
                # check if rule gives user access to button
                rules_for_button = [rule for rule in rules if getattr(rule, 'name', False) == button_name]
                if rules_for_button:

                    # might have multiple rules (from inherited views), so concatenate groups lists
                    groups_with_duplicates = [r.group_ids for r in rules_for_button]
                    groups = []
                    for group in groups_with_duplicates:
                        if isinstance(group, (list, tuple)):
                            for g in group:
                                if g.id not in groups:
                                    groups.append(g.id)

                    access = False

                    if groups:
                        user = self.pool.get('res.users').read(cr, 1, uid, ['groups_id'])
                        if set(user['groups_id']).intersection(groups):
                            access = True
                    else:
                        access = True

                    if access:
                        if 'invisible' in button.attrib:
                            del button.attrib['invisible']
                    else:
                        button.attrib['invisible'] = '1'

    return super_view_look_dom_arch(self, cr, uid, node, view_id, context)

orm.orm_template._orm_template__view_look_dom_arch = view_look_dom_arch

module_whitelist = [
    'ir.module.module',
    'res.log',
    'ir.ui.menu',
    'ir.actions.act_window',
    'ir.ui.view_sc',
    'res.request',
    'ir.model',
    'ir.values',
]

method_whitelist = [
    'read',
    'write',
    'search',
    'fields_view_get',
    'fields_get',
    'name_get',
]


super_execute_cr = osv.object_proxy.execute_cr

def execute_cr(self, cr, uid, obj, method, *args, **kw):

    if uid == 1:
        return super_execute_cr(self, cr, uid, obj, method, *args, **kw)

    # create a fakeuid that will act as an int that will output the admin uid, but also store the users real uid
    adminUid = fakeUid(1, uid)

    if '.' in method:
        module_name = obj.split('.')[0]
    else:
        module_name = obj

    if module_name in module_whitelist or method in method_whitelist:
        return super_execute_cr(self, cr, uid, obj, method, *args, **kw)
    else:
        # load button access rights for this method
        pool = pooler.get_pool(cr.dbname)
        search_obj = [obj]
        if obj == 'sale.order.line':
            search_obj = ['sale.order.line', 'sale.order']
        elif obj == 'purchase.order.line':
            search_obj = ['purchase.order.line', 'purchase.order']
        elif obj == 'signature.line' and args and args[0] and method == 'toggle_active':
            assert len(args[0]) == 1, 'Toggle active can be called on one record only'
            search_obj = [pool.get('signature.line').browse(cr, adminUid, args[0][0], fields_to_fetch=['signature_id']).signature_id.signature_res_model]


        model_id = pool.get('ir.model').search(cr, adminUid, [('model', 'in', search_obj)])
        rules_pool = pool.get('msf_button_access_rights.button_access_rule')
        if rules_pool:
            rules_search = rules_pool.search(cr, adminUid, [('name', '=', method), ('model_id', 'in', model_id)])

            if not rules_search:
                return super_execute_cr(self, cr, uid, obj, method, *args, **kw)

            # do we have rules?
            for rule in rules_pool.browse(cr, adminUid, rules_search):

                # does user have access?
                access = False
                if rule.group_ids:
                    user = pool.get('res.users').read(cr, adminUid, uid)
                    if set(user['groups_id']).intersection([g.id for g in rule.group_ids]):
                        access = True
                else:
                    access = True

                if access:
                    # if method type = action, continue as normal, otherwise
                    if rule.type == 'action':
                        return super_execute_cr(self, cr, uid, obj, method, *args, **kw)

                    # for action type object, the signature is always the same
                    if 'context' in kw:
                        context = kw['context']
                    else:
                        context = args[-1]
                        assert isinstance(context, dict), "Oops! The last argument of call type=object method=%s on object=%s should be a dict! Please contact the developper team." % (method, obj)

                    # continue action as admin user
                    context['real_user'] = uid
                    return super_execute_cr(self, cr, adminUid, obj, method, *args, **kw)


            # throw access denied
            raise osv.except_osv('Access Denied', 'You do not have permission to use this button')

        else:
            logging.getLogger(self._name).warn('Could not get model pool for button_access_rule')
            return super_execute_cr(self, cr, uid, obj, method, *args, **kw)

osv.object_proxy.execute_cr = execute_cr


super_execute_workflow_cr = osv.object_proxy.exec_workflow_cr

def exec_workflow_cr(self, cr, uid, obj, method, *args):

    if uid == 1:
        return super_execute_workflow_cr(self, cr, uid, obj, method, *args)

    # create a fakeuid that will act as an int that will output the admin uid, but also store the users real uid
    adminUid = fakeUid(1, uid)

    if '.' in method:
        module_name = obj.split('.')[0]
    else:
        module_name = obj

    if module_name in module_whitelist or method in method_whitelist:
        return super_execute_workflow_cr(self, cr, uid, obj, method, *args)
    else:
        # load button access rights for this method
        pool = pooler.get_pool(cr.dbname)
        search_obj = [obj]
        if obj == 'sale.order.line':
            search_obj = ['sale.order.line', 'sale.order']
        elif obj == 'purchase.order.line':
            search_obj = ['purchase.order.line', 'purchase.order']

        object_id = pool.get('ir.model').search(cr, adminUid, [('model','in', search_obj)])
        rules_pool = pool.get('msf_button_access_rights.button_access_rule')
        if rules_pool:
            rules_search = rules_pool.search(cr, adminUid, [('name','=',method), ('model_id','in',object_id)])

            if not rules_search:
                return super_execute_workflow_cr(self, cr, uid, obj, method, *args)


            # do we have rules?
            for rule in rules_pool.browse(cr, adminUid, rules_search):
                # does user have access?
                access = False
                if rule.group_ids:
                    user = pool.get('res.users').read(cr, adminUid, uid)
                    if set(user['groups_id']).intersection([g.id for g in rule.group_ids]):
                        access = True
                else:
                    access = True

                if access:
                    # execute workflow as admin
                    return super_execute_workflow_cr(self, cr, adminUid, obj, method, *args)
            # throw access denied
            raise osv.except_osv('Access Denied', 'You do not have permission to use this button')
        else:
            logging.getLogger(self._name).warn('Could not get model pool for button_access_rule')
            return super_execute_workflow_cr(self, cr, uid, obj, method, *args)

osv.object_proxy.exec_workflow_cr = exec_workflow_cr


super_create = orm.orm_memory.create

def create(self, cr, user, vals, context=None):
    return super_create(self, cr, (context or {}).get('real_user', user), vals, context=context)

orm.orm_memory.create = create
