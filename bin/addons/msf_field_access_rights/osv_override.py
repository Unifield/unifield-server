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
from tools import misc
from functools import reduce

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
    if isinstance(domain, str):
        domain = eval(domain)

    # if domain is True or False or empty list, no domain specified, therefore record matches all domains
    if isinstance(domain, bool) or not domain:
        return True

    # add id = record_id to domain
    domain.insert(0, ('id', '=', record_id))
    domain.insert(0, '&')

    # perform search and return bool based on whether or not the record_id was in the
    return record_id in self.search(cr, 1, domain, context={'active_test': False})

class _SetToDefaultFlag:
    pass

# FAR deactivated during sync in US-5123:
#  - never tested
#  - never set on rules for sync user
#  - can create bad behavior during sync if set by mistake
#super_create = orm.orm.create



def infolog(self, cr, uid, message):
    logger = netsvc.Logger()
    logger.notifyChannel(
        'INFOLOG: Model: %s :: User: %s :: ' % (self._name, uid),
        netsvc.LOG_INFO,
        message,
    )
    try:
        oe = self.pool.get('operations.event')
        if oe:
            oe.create(cr, uid, { 'kind': 'infolog', 'data': message })
    except:
        # best effort event logging: do not log errors while logging
        pass

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
    if field_type not in ('many2many', 'one2many') and ((not new_value and current_value) or (new_value and not current_value)):
        return False

    # type specifics...
    if field_type == 'one2many':
        if isinstance(new_value, (list, tuple)):
            if new_value:
                if isinstance(new_value[0], (list, tuple)):
                    return False
            else:
                return True
    if field_type == 'date':
        if current_value and new_value:
            try:
                new_date = datetime.strptime(new_value, '%d/%b/%Y')
                current_date = datetime.strptime(current_value, '%Y-%m-%d')
                if new_date == current_date:
                    return True
            except ValueError:
                logging.getLogger().warn('Could not parse either %s or %s for a date field when checking differences for Field Access Rules' % (current_value, new_value))
    if field_type == 'reference':
        if isinstance(new_value, (list, tuple)):
            if ',' in current_value:
                model, id = current_value.split(',', 1)
                if new_value[0] == id and new_value[1] == model:
                    return True
        if isinstance(new_value, str):
            if ',' in new_value:
                new_model, new_id = new_value.split(',', 1)
                model, id = current_value.split(',', 1)
                if new_id == id and new_model == model:
                    return True
    if field_type == 'many2many':
        if isinstance(new_value, (list, tuple)):
            if new_value:
                if isinstance(new_value[0], (list, tuple)):
                    if isinstance(new_value[0][0], (int, float, complex)):
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
    family_append = family.append
    if hasattr(obj, '_inherits'):
        if obj._inherits:
            for key in obj._inherits:
                if key not in family:
                    family_append(key)
                if key != obj._name:
                    _get_family(obj.pool.get(key), family)

    if hasattr(obj, '_inherit'):
        inh = obj._inherit
        if inh:
            if not isinstance(inh, (list, tuple)):
                inh = [inh]
            for key in inh:
                if key not in family:
                    family_append(key)
                if key != obj._name:
                    _get_family(obj.pool.get(key), family)


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
    if not ids:
        return True

    context = context or {}

    if not isinstance(ids, list):
        ids = [ids]

    update_execution = context.get('sync_update_execution')
    # during sync or with uid=1: do no check FAR
    if uid == 1 or update_execution:
        return super_write(self, cr, uid, ids, vals, context=context)

    # get instance level. if not set, log warning, then return normal write
    instance_level = _get_instance_level(self, cr, uid)
    if not instance_level:
        return super_write(self, cr, uid, ids, vals, context=context)

    # get rules for this model
    rules_pool = self.pool.get('msf_field_access_rights.field_access_rule')
    if not rules_pool:
        return super_write(self, cr, uid, ids, vals, context=context)

    groups = self.pool.get('res.users').read(cr, 1, uid, ['groups_id'], context=context)['groups_id']
    rules_search = _get_rules_for_family(self, cr, rules_pool, instance_level, groups)

    # if have rules
    if rules_search:
        old_values_list = self.read(cr, 1, ids, list(vals.keys()), context=context)
        family = _get_family_names(self, cr, rules_pool, instance_level, groups)
        columns = reduce(lambda x, y: dict(list(x.items()) + list(y.items())), [self.pool.get(model)._columns for model in family])
        fields_blacklist = [
            'nomenclature_description',
        ]

        rules_data = dict(
            (x['id'], x['domain_text']) for x in
            self.pool.get('msf_field_access_rights.field_access_rule').read(cr, uid, rules_search, ['domain_text'], context=context)
        )
        for old_values in old_values_list:
            # keep only the property that changes between old an new values
            dict_diff = dict([(key, value) for key, value in list(vals.items()) if old_values[key] != value])
            diff_properties = list(dict_diff.keys())

            # remove the blacklisted fields
            diff_properties = list(set(diff_properties).difference(fields_blacklist))

            if diff_properties:
                rule_to_check = []
                for rule_id in rules_search:
                    if _record_matches_domain(self, cr, old_values['id'], rules_data[rule_id]):
                        rule_to_check.append(rule_id)

                if rule_to_check:
                    # get the fields with write_access=False
                    cr.execute("""SELECT DISTINCT field_name
                                  FROM msf_field_access_rights_field_access_rule_line
                                  WHERE write_access='f' AND
                                  field_access_rule in %s AND
                                  field_name in %s
                            """, (tuple(rule_to_check), tuple(diff_properties)))
                    no_write_access_fields = [x[0] for x in cr.fetchall()]

                    for field_name in no_write_access_fields:
                        if not _values_equate(columns[field_name]._type,
                                              old_values[field_name], vals[field_name]):
                            # throw access denied error
                            raise osv.except_osv('Access Denied', 'You do not have access to the field (%s). If you did not edit this field, please let an OpenERP administrator know about this error message, and the field name.' % field_name)

        return super_write(self, cr, uid, ids, vals, context=context)
    else:
        return super_write(self, cr, uid, ids, vals, context=context)

orm.orm.write = write


super_fields_view_get = orm.orm.fields_view_get

def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):

    context = context or {}
    fields_view = super_fields_view_get(self, cr, uid, view_id, view_type, context, toolbar, submenu)

    if uid != 1 or self._name == 'purchase.order':

        # get instance level. if not set, log warning, then return normal fields_view
        instance_level = _get_instance_level(self, cr, 1)
        if not instance_level:
            return fields_view

        # get rules for this model
        groups = self.pool.get('res.users').read(cr, 1, uid, ['groups_id'], context=context)['groups_id']

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
                            field.attrib['help'] = '[Field Disabled by Field Access Rights] %s' % (misc.ustr(self._columns[field_name].help))

                # get the modified xml string and return it
                fields_view['arch'] = etree.tostring(view_xml, encoding='unicode')
                return fields_view

            else:
                # no domains
                return fields_view
        else:
            return fields_view

    return fields_view

orm.orm.fields_view_get = fields_view_get
