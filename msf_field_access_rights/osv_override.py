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
from datetime import datetime
import netsvc


def _get_instance_level(self, cr, uid):
    """
    Return instance level linked to this user.
    If section, return 'hq' string instead.
    """
    result = False
    if self.pool.get('msf.instance'):
        sql = """
            SELECT i.level
            FROM res_users AS u, res_company AS c, msf_instance AS i
            WHERE u.company_id = c.id
            AND c.instance_id = i.id
            AND u.id = %s"""
        cr.execute(sql, (uid,))
        result = cr.fetchall()
        if not result or not result[0]:
            return False
        result = result[0][0]
        if result == 'section':
            return 'hq'
    return result

def _record_matches_domain(self, cr, record_id, domain):
    """
    Make a search with domain + id = id. If we get the ID in the result, the domain matches the record
    """
    # convert domain from string to list
    if isinstance(domain, (str, unicode)):
        domain = eval(domain)
        
    # if domain is True or False or empty list, no domain specified, therefore record matches all domains
    if isinstance(domain, bool) or not domain:
        return True
    
    # add id = record_id to domain 
    domain.insert(0, ('id', '=', record_id))
    domain.insert(0, '&')

    # perform search and return bool based on whether or not the record_id was in the 
    return record_id in self.search(cr, 1, domain)

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
    if context.get('sync_update_execution'):
        
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
                    return create_result
                    
                rules_search = rules_pool.search(cr, 1, ['&', ('model_name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])
                

                # do we have rules that apply to this user and model?
                if rules_search:
                    field_changed = False
                    access_line_obj = self.pool.get('msf_field_access_rights.field_access_rule_line')
                    line_ids = access_line_obj.search(cr, uid, [('field_access_rule', 'in', rules_search), ('value_not_synchronized_on_create', '=', True)])
                    if not line_ids:
                        return create_result
                    rules_search = rules_pool.search(cr, 1, [('field_access_rule_line_ids', 'in', line_ids)])
                    rules = rules_pool.browse(cr, 1, rules_search)
                    defaults = self.pool.get(model_name)._defaults

                    # for each rule, check the record against the rule domain.
                    for rule in rules:

                        is_match = True

                        if rule.domain_text:
                            is_match = _record_matches_domain(self, cr, create_result, rule.domain_text)
                        
                        if is_match:
                            # record matches the domain so modify values based on rule lines
                            for line in rule.field_access_rule_line_ids:
                                if line.value_not_synchronized_on_create:
                                    field_changed = True
                                    default_value = defaults.get(line.field.name, None)
                                    new_value = default_value if default_value and not hasattr(default_value, '__call__') else None
                                    vals[line.field.name] = new_value

                    # Then update the record
                    if field_changed:
                        self.write(cr, 1, create_result, vals, context=dict(context, sync_update_execution=False))

                return create_result
            else:
                return create_result
        else:
            return False
    else:
        res = super_create(self, cr, uid, vals, context)
        return res

orm.orm.create = create


def infolog(self, cr, uid, message):
    logger = netsvc.Logger()
    logger.notifyChannel(
       'INFOLOG: Model: %s :: User: %s :: ' % (self._name, uid),
        netsvc.LOG_INFO,
        message,
    )

orm.orm.infolog = infolog
orm.orm_memory.infolog = infolog


def _values_equate(field_type, current_value, new_value):
    """
    discern if two values differ or not, for each file type that is different in the database read() value and the web write vals data value (boring)  
    """
    
    # directly test against each other
    if current_value == new_value:
        return True
    
    # if both evaluate to False, they equate
    if bool(current_value) == False and bool(new_value) == False:
        return True
    
    # if one evals to False and the other does not, they are different
    if field_type != 'many2many' and ((not new_value and current_value) or (new_value and not current_value)):
        return False
    
    # type specifics...
    if field_type == 'one2many':
       if isinstance(new_value, (list, tuple)):
           if new_value:
               if isinstance(new_value[0], (list, tuple)):
                   return False 
    if field_type == 'date':
        if current_value and new_value:
            try:
                new_date = datetime.strptime(new_value, '%d/%b/%Y')
                current_date = datetime.strptime(current_value, '%Y-%m-%d')
                if new_date == current_date:
                    return True
            except ValueError as e:
                logging.getLogger().warn('Could not parse either %s or %s for a date field when checking differences for Field Access Rules' % (current_value, new_value))
    if field_type == 'reference':
        if isinstance(new_value, (list, tuple)):
            if ',' in current_value:
                model, id = current_value.split(',', 1)
                if new_value[0] == id and new_value[1] == model:
                    return True
        if isinstance(new_value, (str, unicode)):
            if ',' in new_value:
                new_model, new_id = new_value.split(',', 1)
                model, id = current_value.split(',', 1)
                if new_id == id and new_model == model:
                    return True
    if field_type == 'many2many':
        if isinstance(new_value, (list, tuple)):
            if new_value:
                if isinstance(new_value[0], (list, tuple)):
                    if isinstance(new_value[0][0], (int, long, float, complex)):
                        if not new_value[0][2]:
                            return True
    if field_type == 'many2one':
        if isinstance(current_value, tuple):
            if current_value[0] == new_value:
                return True
        if isinstance(current_value, osv.orm.browse_record):
            if current_value.id == new_value:
                return True

    return False


def _get_family(obj, family):
    if hasattr(obj, '_inherits'):
        if obj._inherits:
            for key in obj._inherits:
                if key not in family:
                    family.append(key)
                if key != obj._name:
                    _get_family(obj.pool.get(key), family)
            
    if hasattr(obj, '_inherit'):
        if obj._inherit:
            if obj._inherit not in family:
                family.append(obj._inherit)
            if obj._inherit != obj._name:
                _get_family(obj.pool.get(obj._inherit), family)


def _get_rules_for_family(self, cr, rules_pool, instance_level, groups):
    family = [self._name]
    _get_family(self, family)
    return rules_pool.search(cr, 1, ['&', ('model_name', 'in', family), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

def _get_family_names(self, cr, rules_pool, instance_level, groups):
    family = [self._name]
    _get_family(self, family)
    return family

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
        return super_write(self, cr, uid, ids, vals, context=context)

    # get rules for this model
    model_name = self._name
    user = self.pool.get('res.users').browse(cr, 1, uid, context=context)
    groups = [x.id for x in user.groups_id]

    rules_pool = self.pool.get('msf_field_access_rights.field_access_rule')
    if not rules_pool:
        return super_write(self, cr, uid, ids, vals, context=context)
    
    rules_search = _get_rules_for_family(self, cr, rules_pool, instance_level, groups)

    # if have rules
    if rules_search:

        # get rules for this object, the current records values, the names of all parent classes (recursively) and columns for the whole family
        rules = rules_pool.browse(cr, 1, rules_search, context=context)
        current_records = self.read(cr, 1, ids, context=context)
        family = _get_family_names(self, cr, rules_pool, instance_level, groups)
        columns = reduce(lambda x, y: dict(x.items() + y.items()), [self.pool.get(model)._columns for model in family])
        
        fields_blacklist = [
            'nomenclature_description'
        ]

        # check for denied write_access. Loop through current_records and check it against each rule's domain, then search for access denied fields. throw exception if found
        if uid != 1:
            for record in current_records:
                for rule in rules:
                    if _record_matches_domain(self, cr, record['id'], rule.domain_text):
    
                        # rule applies for this record so throw exception if we are trying to edit a field without write_access
                        # for each rule
                        for line in rule.field_access_rule_line_ids:
                            # that has write_access denied
                            if not line.write_access:
                                # check field name blacklist
                                if line.field.name not in fields_blacklist:
                                
                                    # and whose field name is in the new values list
                                    if line.field.name in vals:
                                        
                                        # (accommodate bug where a disabled reference field in web returns a list instead of a comma separated string:)
                                        if line.field.name in columns and columns[line.field.name]._type == 'reference':
                                            if isinstance(vals[line.field.name], (list, tuple)):
                                                if vals[line.field.name][0]:
                                                    vals[line.field.name] = vals[line.field.name][1] + ',' + vals[line.field.name][0]
                                                else:
                                                    vals[line.field.name] = ''
                                            elif vals[line.field.name] and ',' not in vals[line.field.name]:
                                                vals[line.field.name] = record[line.field.name]
                                        
                                        # and whose current value is different from the new value in the new values list
                                        if not _values_equate(columns[line.field.name]._type, record[line.field.name], vals[line.field.name]):
                                            # throw access denied error
                                            raise osv.except_osv('Access Denied', 'You do not have access to the field (%s). If you did not edit this field, please let an OpenERP administrator know about this error message, and the field name.' % line.field.name)

        # if syncing, sanitize editted rows that don't have sync_on_write permission
        if context.get('sync_update_execution'):
            access_line_obj = self.pool.get('msf_field_access_rights.field_access_rule_line')
            line_ids = access_line_obj.search(cr, uid, [('field_access_rule', 'in', rules_search), ('value_not_synchronized_on_write', '=', True)])
            if not line_ids:
                return super_write(self, cr, uid, ids, vals, context=context)
            rule_ids = rules_pool.search(cr, 1, [('field_access_rule_line_ids', 'in', line_ids)])
            rules = rules_pool.browse(cr, 1, rule_ids)
            # iterate over current records 
            for record in current_records:
                new_values = copy.deepcopy(vals)

                # iterate over rules and see if they match the current record
                for rule in rules:
                    if _record_matches_domain(self, cr, record['id'], rule.domain_text):

                        # for each rule, if value has changed and value_not_synchronized_on_write then delete key from new_values
                        for line in rule.field_access_rule_line_ids:
                            # if value_not_synchronized_on_write
                            if line.value_not_synchronized_on_write:
                                # if we have a new value for the field
                                if line.field.name in new_values:
                                    # if the current field value is different from the new field value
                                    if line.field.name in record:
                                        if new_values[line.field.name] != record[line.field.name]:
                                            # remove field from new_values
                                            del new_values[line.field.name]
                                    else:
                                        del new_values[line.field.name]

                # if we still have new values to write, write them for the current record
                if new_values:
                    super_write(self, cr, uid, record['id'], new_values, context=context)
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
            return fields_view

        # get rules for this model
        model_name = self._name
        user = self.pool.get('res.users').browse(cr, 1, uid, context=context)
        groups = [x.id for x in user.groups_id]

        rules_pool = self.pool.get('msf_field_access_rights.field_access_rule')
        if not rules_pool:
            return fields_view
        
        rules_search = _get_rules_for_family(self, cr, rules_pool, instance_level, groups)
    
        # if have rules
        if rules_search:
            rules = rules_pool.browse(cr, 1, rules_search, context=context)

            # get a dictionary of domains with field names as the key and the value being a concatenation of rule domains, or True if universal
            domains = {}
            for rule in rules:
                for line in rule.field_access_rule_line_ids:
                    if not line.write_access:
                        if domains.get(line.field.name, False) != True:
                            if rule.domain_text and rule.domain_text != '[]':
                                if domains.get(line.field.name, []):
                                    domains[line.field.name] = ['|'] + domains.get(line.field.name, []) + (eval(rule.domain_text))
                                else:
                                    domains[line.field.name] = eval(rule.domain_text)
                            else:
                                domains[line.field.name] = True
            # Edit the view xml by adding the rule domain to the rule's field if that field is in the xml
            if domains:

                # parse the view xml
                view_xml_text = fields_view['arch']
                view_xml = etree.fromstring(view_xml_text)

                # loop through domains looking for field in xml and editting their readonly attributes
                for field_name in domains:
                    domain_value = domains[field_name]

                    domain_value_or = copy.deepcopy(domain_value)
                    if isinstance(domain_value_or, (list, tuple)) and len(domain_value_or) > 0:
                        domain_value_or.insert(0, '|')

                    # get field from xml using xpath
                    fields = view_xml.xpath("//field[@name='%s']" % field_name)

                    # if field is not already readonly, add/edit attrs
                    for field in fields:
                        if not field.get('readonly', False):

                            # applicable to all so set readonly
                            if domain_value == True:
                                field.set('readonly', '1')
                                
                                # remove attrs if present
                                if 'attrs' in field.attrib:
                                    attrs_text = field.attrib['attrs']
                                    if 'readonly' in attrs_text:
                                        attrs = eval(attrs_text)
                                        del attrs['readonly']
                                        field.set('attrs', str(attrs))
                            else:
                                # find attrs
                                attrs_text = field.get('attrs', False)

                                if attrs_text:
                                    # add / modify existing readonly key
                                    attrs = eval(attrs_text)
                                    if attrs.get('readonly', False):
                                        # concatenate domain with existing domains
                                        if isinstance(attrs.get('readonly'), (tuple, list)):
                                            new_dom = domain_value_or + attrs['readonly']
                                            attrs['readonly'] = new_dom
                                        else:
                                            attrs['readonly'] = domain_value
                                    else:
                                        attrs['readonly'] = domain_value

                                    field.set('attrs', str(attrs))
                                else:
                                    field.set('attrs', str( {'readonly': domain_value} ))

                        # add 'hidden by field access rules' flag
                        if field_name in self._columns:
                            field.attrib['help'] = '[Field Disabled by Field Access Rights] ' + self._columns[field_name].help
                
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
