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
import logging
import copy

debug = True

create_debug = False
write_debug = True
fields_debug = False

sync_debug = False
user_debug = False # Warning - this causes some problems because the write within the create function will be filtered as if not being called by an admin 

def dprint(string):
    if debug:
        print string

def cprint(string):
    if create_debug:
        dprint(string)

def wprint(string):
    if write_debug:
        dprint(string)

def fprint(string):
    if fields_debug:
        dprint(string)

def _get_instance_level(self, cr, uid):
    instance_pool = self.pool.get('msf.instance')
    instance_level_search = instance_pool.search(cr, uid, [('level', '!=', False)])
    instance_level = instance_pool.browse(cr, uid, instance_level_search[0]).level

    if instance_level == 'section':
        instance_level = 'hq'

    return instance_level.lower()

def _record_matches_domain(self, cr, uid, record_id, domain):
    """
    Make a search with domain + id = id. If we get the ID in the result, the domain matches the record
    """
    if isinstance(domain, (str, unicode)):
        if len(domain) == 0:
            domain = False
        else:
            domain = eval(domain)
            domain.append(('id', '=', record_id))
            domain.append('&')
            domain.reverse()
    if isinstance(domain, bool):
        return True

    return bool(self.search(cr, uid, domain))

class _SetToDefaultFlag:
    pass

super_create = orm.orm.create

def create(self, cr, uid, vals, context=None):
    """
    If rules defined for current user and model, create each record then check domain for each record.
    If domain matches, for each field with value_not_synchronized_on_create in the rule, update created field with default values.
    """

    cprint('')
    cprint('=================== CREATE OVERRIDE')
    cprint('=== CONTEXT: ')
    cprint(context)
    cprint('=== VALS: ')
    cprint(vals)
    cprint('=== UID: ')
    cprint(uid)
    cprint('')
    cprint('')

    context = context or {}

    # is the create coming from a sync or import? If yes, apply rules from msf_access_right module
    # TODO: remove the testing lines below
    if sync_debug:
        context['sync_data'] = True
        
    if user_debug:
        real_uid = uid
        uid = 0
        
    if (uid != 1 or context.get('applyToAdmin', False)) and context.get('sync_data'):
        
        if user_debug: 
            uid = real_uid

        cprint('====== SYNCING')

        # create the record. we will sanitize it later based on domain search check
        create_result = super_create(self, cr, uid, vals, context)

        if create_result:

            instance_level = _get_instance_level(self, cr, uid)

            cprint('=== INSTANCE_LEVEL: ' + instance_level)

            if instance_level:

                # get rules for this model
                model_name = self._name
                user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
                groups = [x.id for x in user.groups_id]

                rules_pool = self.pool.get('msf_access_rights.field_access_rule')
                rules_search = rules_pool.search(cr, uid, ['&', ('model_name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

                cprint('=== MODEL: ' + model_name)
                cprint('=== USER: ' + str(user))
                cprint('=== GROUPS: ' + str(groups))
                cprint('====== RULES_SEARCH: ' + str(rules_search))

                # do we have rules that apply to this user and model?
                if rules_search:

                    rules = rules_pool.browse(cr, uid, rules_search)

                    # for each rule, check the record against the rule domain.
                    for rule in rules:

                        cprint('=== DOMAIN TEXT: %s' % rule.domain_text)

                        is_match = True

                        if rule.domain_text:
                            is_match = _record_matches_domain(self, cr, uid, create_result, rule.domain_text)
                        
                        cprint('=== IS_MATCH: ' + str(is_match))

                        if is_match:
                            
                            # if record matches the domain, modify values based on rule lines
                            defaults = self.pool.get(model_name)._defaults
                            no_sync_vals = [line for line in rule.field_access_rule_line_ids if line.value_not_synchronized_on_create]
                            
                            for line in no_sync_vals:
                                new_def_val = defaults.get(line.field.name, None)
                                new_val = new_def_val if not hasattr(new_def_val, '__call__') else None
                                vals[line.field.name] = new_val

                    # Then update the record
                    self.write(cr, 1, create_result, vals, context=context.update({'sync_data':False}))

                return create_result
            else:
                logging.getLogger(self._name).warn('No instance name defined! Until one has been defined in msf.instance, no Field Access Rules can be respected!')
                return create_result

        else:
            return False

    else:
        res = super_create(self, cr, uid, vals, context)
        return res

orm.orm.create = create

super_write = orm.orm.write

def write(self, cr, uid, ids, vals, context=None):
    """
    Check if user has write_access for each field in target record with applicable Field Access Rules. If not, throw exception.
    Also if syncing, check if field value should be synced on write, based on Field Access Rules.
    """

    context = context or {}

    if sync_debug:
        context['sync_data'] = True
        
    if user_debug:
        real_uid = uid
        uid = 0
    
    if (uid != 1 or context.get('applyToAdmin', False)):
        
        if user_debug:
            uid = real_uid

        wprint('================== WRITE OVERRIDE')

        # get instance level. if not set, log warning, then return normal write
        instance_level = _get_instance_level(self, cr, uid)
        if not instance_level:
            logging.getLogger(self._name).warn('No instance name defined! Until one has been defined in msf.instance, no Field Access Rules can be respected!')
            return super_write(self, cr, uid, ids, vals, context=context)

        # get rules for this model
        model_name = self._name
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        groups = [x.id for x in user.groups_id]

        rules_pool = self.pool.get('msf_access_rights.field_access_rule')
        rules_search = rules_pool.search(cr, uid, ['&', ('model_name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

        wprint('=== INSTANCE_LEVEL: ' + instance_level)
        wprint('=== MODEL: ' + model_name)
        wprint('=== USER: ' + str(user))
        wprint('=== GROUPS: ' + str(groups))
        wprint('=== RULES_SEARCH: ' + str(rules_search))
        wprint('=== IDS: ' + str(ids))

        # if have rules
        if rules_search:

            rules = rules_pool.browse(cr, uid, rules_search, context=context)
            current_records = self.browse(cr, uid, ids, context=context)

            # check for denied write_access. Loop through current_records and check it against each rule's domain, then search for access denied fields. throw exception if found
            for record in current_records:
                for rule in rules:
                    if _record_matches_domain(self, cr, uid, record.id, rule.domain_text):

                        # rule applies for this record so throw exception if we are trying to edit a field without write_access
                        access_denied_fields = [line for line in rule.field_access_rule_line_ids if not line.write_access and line.field.name in vals and (getattr(record, line.field.name, vals[line.field.name]) != vals[line.field.name] and not (bool(getattr(record, line.field.name, vals[line.field.name])) == bool(vals[line.field.name])))]
                        if access_denied_fields:
                            wprint('====== ACCESS_DENIED_FIELDS: ' + str([line.field.name for line in access_denied_fields]))
                            wprint('====== VALS: ' + str(vals))
                            wprint('====== EXISTING VALS: %s' % [ str(line.field.name) + ': ' + str(getattr(record, line.field.name)) + ', ' for line in rule.field_access_rule_line_ids ])
                            raise osv.except_osv('Access Denied', 'You are trying to edit a value that you don\'t have access to edit')

            # if syncing, sanitize editted rows that don't have sync_on_write permission
            if context.get('sync_data') or user.login == 'msf_access_rights_benchmarker':

                wprint('====== SYNCING')

                # iterate over current records 
                for record in current_records:
                    new_values = copy.deepcopy(vals)

                    # iterate over rules and see if they match the current record
                    for rule in rules:
                        if _record_matches_domain(self, cr, uid, record.id, rule.domain_text):

                            wprint('=== MATCHING RULE ID: %s' % rule.id)

                            # rule applies for this record so delete key from new values if key is value_not_synchronized_on_write and the value is different from the existing record field
                            no_sync_fields = [line for line in rule.field_access_rule_line_ids \
                            if line.value_not_synchronized_on_write and \
                            line.field.name in vals and \
                            hasattr(record, line.field.name) and \
                            vals[line.field.name] != getattr(record, line.field.name)]

                            for line in no_sync_fields:
                                del new_values[line.field.name]

                            if len(new_values) != len(vals):
                                wprint('=== REMOVED KEYS..')
                                wprint(list(set(vals) - set(new_values)))
                    
                    # if we still have new values to write, write them for the current record
                    if new_values:
                        super_write(self, cr, uid, ids, new_values, context=context)

            return True

        else:
            return super_write(self, cr, uid, ids, vals, context=context)

    else:
        return super_write(self, cr, uid, ids, vals, context=context)

orm.orm.write = write


super_fields_view_get = orm.orm.fields_view_get

def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):

    context = context or {}
    fields_view = super_fields_view_get(self, cr, uid, view_id, view_type, context, toolbar, submenu)

    real_uid = uid
    uid = 0
    if uid != 1:
        uid = real_uid

        fprint('=================== FIELDS_VIEW_GET OVERRIDE')

        # get instance level. if not set, log warning, then return normal fields_view
        instance_level = _get_instance_level(self, cr, uid)
        if not instance_level:
            logging.getLogger(self._name).warn('No instance name defined! Until one has been defined in msf.instance, no Field Access Rules can be respected!')
            return fields_view

        # get rules for this model
        model_name = self._name
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        groups = [x.id for x in user.groups_id]

        rules_pool = self.pool.get('msf_access_rights.field_access_rule')
        rules_search = rules_pool.search(cr, uid, ['&', ('model_name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

        fprint('=== INSTANCE_LEVEL: ' + instance_level)
        fprint('=== MODEL: ' + model_name)
        fprint('=== USER: ' + str(user))
        fprint('=== GROUPS: ' + str(groups))
        fprint('=== RULES_SEARCH: ' + str(rules_search))

        # if have rules
        if rules_search:
            rules = rules_pool.browse(cr, uid, rules_search, context=context)

            # get a dictionary of domains with field names as the key and the value being a concatenation of rule domains, or True if universal
            domains = {}
            for rule in rules:
                for line in [line for line in rule.field_access_rule_line_ids if not line.write_access]:
                    if domains.get(line.field.name, False) != True:
                        if rule.domain_text:
                            domains[line.field.name] = domains.get(line.field.name, []) + (eval(rule.domain_text))
                        else:
                            domains[line.field.name] = True

            fprint('=== DOMAINS... ')
            fprint(domains)

            # modify xml by adding domains to fields
            if domains:

                # parse the view xml
                view_xml_text = fields_view['arch']
                view_xml = etree.fromstring(view_xml_text)

                # loop through domains looking for matching fields and editting attributes
                for domain_key in domains:
                    domain_value = domains[domain_key]

                    domain_value_or = copy.deepcopy(domain_value)
                    if not isinstance(domain_value_or, bool) and len(domain_value_or) > 1:
                        domain_value_or.append('|')
                        domain_value_or.reverse()

                    fprint('=== DOMAINS OR... ')
                    fprint(domain_value_or)

                    fprint('====== MODIFYING FIELD: %s' % domain_key)

                    # get field from xml using xpath
                    fields = view_xml.xpath("//field[@name='%s']" % domain_key)

                    # if field is not already readonly, add/edit attrs
                    for field in fields:
                        if not field.get('readonly', False):

                            fprint('...not readonly')
                            
                            # applicable to all so set readonly
                            if domain_value == True:
                                fprint('...domain_value = True')
                                field.set('readonly', '1')
                            else:
                                # find attrs
                                attrs_text = field.get('attrs', False)

                                if attrs_text:
                                    fprint('...got attrs_text')
                                    # add / modify existing readonly key
                                    attrs = eval(attrs_text)
                                    if attrs.get('readonly', False):
                                        # concatenate domain with existing domains
                                        fprint('...got existing readonly domain')
                                        attrs['readonly'] = attrs['readonly'] + domain_value
                                        attrs['readonly'].append('|')
                                        attrs['readonly'].reverse()
                                    else:
                                        fprint('...add readonly key')
                                        attrs['readonly'] = str( domain_value_or )

                                    field.set('attrs', str(attrs))
                                else:
                                    field.set('attrs', str( {'readonly': domain_value_or} ))
                                    fprint('...set new attrs')

                        fprint('=== MODIFIED FIELD...')
                        fprint(etree.tostring(field))

                # get the modified xml string and return it
                fields_view['arch'] = etree.tostring(view_xml)
                fprint('====== RETURNING XML..')
                fprint(etree.tostring(view_xml))
                fprint('====== RETURNING OBJECT..')
                fprint(fields_view)
                return fields_view

        else:
            return fields_view

    return fields_view

orm.orm.fields_view_get = fields_view_get