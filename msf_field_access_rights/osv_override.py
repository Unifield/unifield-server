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

def _get_instance_level(self, cr, uid):
    instance = self.pool.get('res.users').browse(cr, 1, uid).company_id.instance_id
    instance_level = getattr(instance, 'level', False)
    
    if instance_level:
        if instance_level.lower() == 'section':
            instance_level = 'hq'

        return instance_level.lower()
    return False

def _record_matches_domain(self, cr, record_id, domain):
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

    return bool(self.search(cr, 1, domain))

class _SetToDefaultFlag:
    pass

super_create = orm.orm.create

def create(self, cr, uid, vals, context=None):
    """
    If rules defined for current user and model, create each record then check domain for each record.
    If domain matches, for each field with value_not_synchronized_on_create in the rule, update created field with default values.
    """
    context = context or {}

    # is the create coming from a sync or import? If yes, apply rules from msf_access_right module
    if context.get('sync_data'):
        
        # create the record. we will sanitize it later based on domain search check
        create_result = super_create(self, cr, uid, vals, context)

        if create_result:
            instance_level = _get_instance_level(self, cr, uid)

            if instance_level:

                # get rules for this model, instance and user
                model_name = self._name
                user = self.pool.get('res.users').browse(cr, 1, uid, context=context)
                groups = [x.id for x in user.groups_id]

                rules_pool = self.pool.get('msf_field_access_rights.field_access_rule')
                if not rules_pool:
                    logging.getLogger(self._name).warn("Could not get msf_field_access_rights.field_access_rule pool, so no rules have been implemented!")
                    return create_result
                    
                rules_search = rules_pool.search(cr, 1, ['&', ('model_name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])
                
                defaults = self.pool.get(model_name)._defaults

                # do we have rules that apply to this user and model?
                if rules_search:
                    rules = rules_pool.browse(cr, 1, rules_search)

                    # for each rule, check the record against the rule domain.
                    for rule in rules:

                        is_match = True

                        if rule.domain_text:
                            is_match = _record_matches_domain(self, cr, create_result, rule.domain_text)
                        
                        if is_match:
                            # record matches the domain so modify values based on rule lines
                            for line in rule.field_access_rule_line_ids:
                                if line.value_not_synchronized_on_create:
                                    default_value = defaults.get(line.field.name, None)
                                    new_value = default_value if default_value and not hasattr(default_value, '__call__') else None
                                    vals[line.field.name] = new_value

                    # Then update the record
                    self.write(cr, 1, create_result, vals, context=context.update({'sync_data':False}))

                return create_result
            else:
                logging.getLogger(self._name).warn("No instance name for current user's company. Function: create, Model: %s" % self._name)
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
    
    if not isinstance(ids, list):
        ids = [ids]

    # get instance level. if not set, log warning, then return normal write
    instance_level = _get_instance_level(self, cr, uid)
    if not instance_level:
        logging.getLogger(self._name).warn("No instance name for current user's company. Function: write, Model: %s" % self._name)
        return super_write(self, cr, uid, ids, vals, context=context)

    # get rules for this model
    model_name = self._name
    user = self.pool.get('res.users').browse(cr, 1, uid, context=context)
    groups = [x.id for x in user.groups_id]

    rules_pool = self.pool.get('msf_field_access_rights.field_access_rule')
    if not rules_pool:
        logging.getLogger(self._name).warn("Could not get msf_field_access_rights.field_access_rule pool, so no rules have been implemented!")
        return super_write(self, cr, uid, ids, vals, context=context)
    
    rules_search = rules_pool.search(cr, 1, ['&', ('model_name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

    # if have rules
    if rules_search:

        rules = rules_pool.browse(cr, 1, rules_search, context=context)
        current_records = self.browse(cr, 1, ids, context=context)

        # check for denied write_access. Loop through current_records and check it against each rule's domain, then search for access denied fields. throw exception if found
        if uid != 1:
            for record in current_records:
                for rule in rules:
                    if _record_matches_domain(self, cr, record.id, rule.domain_text):
    
                        # rule applies for this record so throw exception if we are trying to edit a field without write_access
                        # for each rule
                        for line in rule.field_access_rule_line_ids:
                            # that has write_access denied
                            if not line.write_access:
                                # and whose field name is in the new values list
                                if line.field.name in vals:
                                    # and whose current value is different from the new value in the new values list
                                    if getattr(record, line.field.name, vals[line.field.name]) != vals[line.field.name]:
                                        # (in this case, values resolving to False, equate. For example, False == None)
                                        if not (bool(getattr(record, line.field.name, vals[line.field.name])) == False and bool(vals[line.field.name]) == False):
                                            # throw access denied error
                                            raise osv.except_osv('Access Denied', 'You are trying to edit a value that you don\'t have access to edit')

        # if syncing, sanitize editted rows that don't have sync_on_write permission
        if context.get('sync_data') or user.login == 'msf_field_access_rights_benchmarker':

            # iterate over current records 
            for record in current_records:
                new_values = copy.deepcopy(vals)

                # iterate over rules and see if they match the current record
                for rule in rules:
                    if _record_matches_domain(self, cr, record.id, rule.domain_text):

                        # for each rule, if value has changed and value_not_synchronized_on_write then delete key from new_values
                        for line in rule.field_access_rule_line_ids:
                            # if value_not_synchronized_on_write
                            if line.value_not_synchronized_on_write:
                                # if we have a new value for the field
                                if line.field.name in new_values:
                                    # if the current field value is different from the new field value
                                    if hasattr(record, line.field.name):
                                        if new_values[line.field.name] != getattr(record, line.field.name):
                                            # remove field from new_values
                                            del new_values[line.field.name]
                                    else:
                                        del new_values[line.field.name]

                # if we still have new values to write, write them for the current record
                if new_values:
                    super_write(self, cr, uid, record.id, new_values, context=context)
        else:
            return super_write(self, cr, uid, ids, vals, context=context)
    else:
        return super_write(self, cr, uid, ids, vals, context=context)

orm.orm.write = write


super_fields_view_get = orm.orm.fields_view_get

def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):

    context = context or {}
    fields_view = super_fields_view_get(self, cr, uid, view_id, view_type, context, toolbar, submenu)

    if uid != 1:

        # get instance level. if not set, log warning, then return normal fields_view
        instance_level = _get_instance_level(self, cr, 1)
        if not instance_level:
            logging.getLogger(self._name).warn("No instance name for current user's company. Function: field_view_get, Model: %s" % self._name)
            return fields_view

        # get rules for this model
        model_name = self._name
        user = self.pool.get('res.users').browse(cr, 1, uid, context=context)
        groups = [x.id for x in user.groups_id]

        rules_pool = self.pool.get('msf_field_access_rights.field_access_rule')
        if not rules_pool:
            logging.getLogger(self._name).warn("Could not get msf_field_access_rights.field_access_rule pool, so no rules have been implemented!")
            return fields_view
    
        rules_search = rules_pool.search(cr, 1, ['&', ('model_name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

        # if have rules
        if rules_search:
            rules = rules_pool.browse(cr, 1, rules_search, context=context)

            # get a dictionary of domains with field names as the key and the value being a concatenation of rule domains, or True if universal
            domains = {}
            for rule in rules:
                for line in rule.field_access_rule_line_ids:
                    if not line.write_access:
                        if domains.get(line.field.name, False) != True:
                            if rule.domain_text:
                                domains[line.field.name] = domains.get(line.field.name, []) + (eval(rule.domain_text))
                            else:
                                domains[line.field.name] = True

            # Edit the view xml by adding the rule domain to the rule's field if that field is in the xml
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


                    # get field from xml using xpath
                    fields = view_xml.xpath("//field[@name='%s']" % domain_key)

                    # if field is not already readonly, add/edit attrs
                    for field in fields:
                        if not field.get('readonly', False):

                            
                            # applicable to all so set readonly
                            if domain_value == True:
                                field.set('readonly', '1')
                                
                                # remove attrs if present
                                del field.attrib['attrs']
                            else:
                                # find attrs
                                attrs_text = field.get('attrs', False)

                                if attrs_text:
                                    # add / modify existing readonly key
                                    attrs = eval(attrs_text)
                                    if attrs.get('readonly', False):
                                        # concatenate domain with existing domains
                                        attrs['readonly'] = attrs['readonly'] + domain_value
                                        attrs['readonly'].append('|')
                                        attrs['readonly'].reverse()
                                    else:
                                        attrs['readonly'] = str( domain_value_or )

                                    field.set('attrs', str(attrs))
                                else:
                                    field.set('attrs', str( {'readonly': domain_value_or} ))

                # get the modified xml string and return it
                fields_view['arch'] = etree.tostring(view_xml)
                return fields_view
            
            else:
                # no domains
                return fields_view
        else:
            return fields_view

    return fields_view

orm.orm.fields_view_get = fields_view_get