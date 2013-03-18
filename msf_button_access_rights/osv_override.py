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
from lxml import etree
import pooler
import random
import string

super_fields_view_get = orm.orm.fields_view_get

def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
    """
    Dynamically change button groups based on button access rules
    """

    context = context or {}
    fields_view = super_fields_view_get(self, cr, uid, view_id, view_type, context, toolbar, submenu)
    view_id = view_id or fields_view.get('view_id', False)
    
    if uid != 1:
        
        rules_pool = self.pool.get('msf_button_access_rights.button_access_rule')
        
        # view_id == 0 if view generated on fly by openerp because no custom view specified, therefore we will have no rules
        if view_id:
            search_ids = rules_pool._get_family_ids(cr, view_id)
        else:
            return fields_view
        
        rules_search = rules_pool.search(cr, 1, [('view_id', 'in', search_ids)])

        # if have rules
        if rules_search:
            rules = rules_pool.browse(cr, 1, rules_search, context=context)
            
            # parse view and get all buttons with a name, a type that is not 'special', no position attribute, and may or may not have an invisible attribute (But not set to '1')
            view_xml = etree.fromstring(fields_view['arch'])
            buttons = view_xml.xpath("//button[ @name and @type != 'special' and not (@position) and @invisible != '1' or not (@invisible) ]")
            
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
                        user = self.pool.get('res.users').read(cr, 1, uid)
                        if set(user['groups_id']).intersection(groups):
                            access = True
                    else:
                        access = True
                            
                    if access:
                        if 'invisible' in button.attrib:
                            del button.attrib['invisible']
                    else:
                        button.attrib['invisible'] = '1'
                            
            fields_view['arch'] = etree.tostring(view_xml)
            
            return fields_view

        else:
            return fields_view

    else:
        return fields_view

orm.orm.fields_view_get = fields_view_get

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
    
    if '.' in method:
        module_name = obj.split('.')[0]
    else:
        module_name = obj
    
    if module_name in module_whitelist or method in method_whitelist:
        return super_execute_cr(self, cr, uid, obj, method, *args, **kw)
    else:
        # load button access rights for this method
        pool = pooler.get_pool(cr.dbname) 
        model_id = pool.get('ir.model').search(cr, 1, [('model','=',obj)])
        rules_pool = pool.get('msf_button_access_rights.button_access_rule')
        if rules_pool:
            rules_search = rules_pool.search(cr, 1, [('name','=',method),('model_id','=',model_id)])
            
            # do we have rules?
            if rules_search:
                rule = rules_pool.browse(cr, 1, rules_search[0])
                
                # does user have access? 
                access = False
                if rule.group_ids:
                    user = pool.get('res.users').read(cr, 1, uid)
                    if set(user['groups_id']).intersection([g.id for g in rule.group_ids]):
                        access = True
                else:
                    access = True
                
                if access:
                    # if method type = action, continue as normal, otherwise
                    if rule.type == 'action':
                        return super_execute_cr(self, cr, uid, obj, method, *args, **kw)
                
                    # for action type object, the signature is always the same
                    if rule.type == 'object' and 'context' not in kw:
                        args, kw['context'] = args[:-1], args[-1]
                        assert isinstance(kw['context'], dict), "Oops! The last argument of call type=object method=%s on object=%s should be a dict! Please contact the developper team." % (method, obj)

                    # continue action as admin user
                    kw['context']['real_user'] = uid
                    return super_execute_cr(self, cr, 1, obj, method, *args, **kw)
                    
                else:
                    # throw access denied
                    raise osv.except_osv('Access Denied', 'You do not have permission to use this button')
                
            else:
                return super_execute_cr(self, cr, uid, obj, method, *args, **kw)
        else:
            logging.getLogger(self._name).warn('Could not get model pool for button_access_rule')
            return super_execute_cr(self, cr, uid, obj, method, *args, **kw)

osv.object_proxy.execute_cr = execute_cr


super_execute_workflow_cr = osv.object_proxy.exec_workflow_cr

def exec_workflow_cr(self, cr, uid, obj, method, *args):

    if uid == 1:
        return super_execute_workflow_cr(self, cr, uid, obj, method, *args)

    if '.' in method:
        module_name = obj.split('.')[0]
    else:
        module_name = obj
    
    if module_name in module_whitelist or method in method_whitelist:
        return super_execute_workflow_cr(self, cr, uid, obj, method, *args)
    else:
        # load button access rights for this method
        pool = pooler.get_pool(cr.dbname) 
        object_id = pool.get('ir.model').search(cr, 1, [('model','=',obj)])
        rules_pool = pool.get('msf_button_access_rights.button_access_rule')
        if rules_pool:
            rules_search = rules_pool.search(cr, 1, [('name','=',method),('model_id','=',object_id)])
            
            # do we have rules?
            if rules_search:
                rule = rules_pool.browse(cr, 1, rules_search[0])
                
                # does user have access? 
                access = False
                if rule.group_ids:
                    user = pool.get('res.users').read(cr, 1, uid)
                    if set(user['groups_id']).intersection([g.id for g in rule.group_ids]):
                        access = True
                else:
                    access = True
                
                if access:
                    # execute workflow as admin
                    return super_execute_workflow_cr(self, cr, 1, obj, method, *args)
                else:
                    # throw access denied
                    raise osv.except_osv('Access Denied', 'You do not have permission to use this button')
            else:
                return super_execute_workflow_cr(self, cr, uid, obj, method, *args)
        else:
            logging.getLogger(self._name).warn('Could not get model pool for button_access_rule')
            return super_execute_workflow_cr(self, cr, uid, obj, method, *args)
    
osv.object_proxy.exec_workflow_cr = exec_workflow_cr


super_create = orm.orm_memory.create
orm.orm_memory.create = lambda self, cr, user, vals, context=None: super_create(self, cr, (context or {}).get('real_user', user), vals, context=context)
