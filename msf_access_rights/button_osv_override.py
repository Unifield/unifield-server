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

def groups_to_names(cr, pool, groups):
    data_pool = pool.get('ir.model.data')
    group_ids = [group.id for group in groups]
    
    # get groups xml ids
    group_xml_ids_search = data_pool.search(cr, 1, [('model','=','res.groups'),('res_id','in',group_ids)])
    group_xml_ids = data_pool.browse(cr, 1, group_xml_ids_search)
    
    # create xml_id for groups that do not have one
    for group in groups:
        create_xml_id = True
        for g in group_xml_ids:
            if group.id == g.res_id:
                create_xml_id = False
        
        if create_xml_id:
            data_id = data_pool.create(cr, 1, {'name':group.name.replace(' ','_') + '_' + random_string(), 'module':'base', 'model': 'res.groups', 'res_id': group.id})
            group_xml_ids.append(data_pool.browse(cr, 1, data_id))
    
    ret = ','.join([g.module + '.' + g.name if g.module else g.name for g in group_xml_ids])    
    return ret

def random_string():
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(10))

super_fields_view_get = orm.orm.fields_view_get

def button_fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
    """
    Dynamically change button groups based on button access rules
    """

    context = context or {}
    fields_view = super_fields_view_get(self, cr, uid, view_id, view_type, context, toolbar, submenu)
    view_id = view_id or fields_view.get('view_id', False)

    if uid != 0:

        rules_pool = self.pool.get('msf_access_rights.button_access_rule')
        rules_search = rules_pool.search(cr, 1, [('view_id', '=', view_id)]) # TODO: extend to get all inherited views too

        # if have rules
        if rules_search:
            rules = rules_pool.browse(cr, 1, rules_search, context=context)
            
            # parse view and get all buttons
            view_xml = etree.fromstring(fields_view['arch'])
            buttons = view_xml.xpath("//button")
            
            for button in buttons:
                
                # ignore buttons with the position attribute
                if button.attrib.get('position', False):
                    continue
                
                button_name = button.attrib.get('name', '')
                if not button_name: 
                    continue
                
                # add / edit groups attribute to include groups defined in the rule
                rules_for_button = [rule for rule in rules if getattr(rule, 'name', False) == button_name]
                for rule in rules_for_button:
                    if rule.group_ids:
                        if button.attrib.get('groups', False):
                            # append to existing
                            existing_groups = button.attrib.get('groups','')
                            button.attrib['groups'] = existing_groups + ',' + groups_to_names(cr, self.pool, rule.group_ids)
                        else:
                            # create groups tag
                            button.attrib['groups'] = groups_to_names(cr, self.pool, rule.group_ids)
                
            fields_view['arch'] = etree.tostring(view_xml)
            
            return fields_view

        else:
            return fields_view

    else:
        return fields_view

orm.orm.fields_view_get = button_fields_view_get

module_whitelist = [
    'ir.module.module',
    'res.log',
    'res.users',
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
    if '.' in method:
        module_name = obj.split('.')[0]
    else:
        module_name = obj
    
    if module_name in module_whitelist or method in method_whitelist:
        return super_execute_cr(self, cr, uid, obj, method, *args, **kw)
    else:
        # load button access rights for this method
        pool = pooler.get_pool(cr.dbname) 
        object_id = pool.get('ir.model').search(cr, 1, [('model','=',obj)])
        rules_pool = pool.get('msf_access_rights.button_access_rule')
        rules_search = rules_pool.search(cr, 1, [('name','=',method),('model_id','=',object_id)])
        
        # do we have rules?
        if rules_search:
            rule = rules_pool.browse(cr, 1, rules_search[0])
            
            # does user have access? 
            access = False
            if rule.group_ids:
                user = pool.get('res.users').read(cr, 1, uid)
                if set(user['groups_id']).intersection(rule.group_ids):
                    access = True
            else:
                access = True
            
            if access:
                # if method type = action, continue as normal, otherwise
                if rule.type == 'action':
                    return super_execute_cr(self, cr, uid, obj, method, *args, **kw)
            
                # continue action as admin user
                if rule.type != 'action':
                    return super_execute_cr(self, cr, 1, obj, method, *args, **kw)
                
            else:
                # throw access denied
                raise osv.except_osv('Access Denied', 'You do not have permission to use this button')
            
        else:
            return super_execute_cr(self, cr, uid, obj, method, *args, **kw)

osv.object_proxy.execute_cr = execute_cr


super_execute_workflow_cr = osv.object_proxy.exec_workflow_cr

def exec_workflow_cr(self, cr, uid, obj, method, *args):
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
        rules_pool = pool.get('msf_access_rights.button_access_rule')
        rules_search = rules_pool.search(cr, 1, [('name','=',method),('model_id','=',object_id)])
        
        # do we have rules?
        if rules_search:
            rule = rules_pool.browse(cr, 1, rules_search[0])
            
            # does user have access? 
            access = False
            if rule.group_ids:
                user = pool.get('res.users').read(cr, 1, uid)
                if set(user['groups_id']).intersection(rule.group_ids):
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
    
osv.object_proxy.exec_workflow_cr = exec_workflow_cr