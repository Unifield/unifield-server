#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
import logging
import copy

super_create = orm.orm.create


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
        domain = eval(domain)
        domain.append(('id', '=', record_id))
        domain.append('&')
        domain.reverse()
    
    return bool(self.search(cr, uid, domain))

def create(self, cr, uid, vals, context=None):
    """
    If rules defined for current user and model, create each record then check domain for each record.
    If domain matches, for each field with value_not_synchronized_on_create in the rule, update created field with default values.
    """

    print ''
    print '=================== CREATE OVERRIDE'
    print '=== CONTEXT: '
    print context
    print '=== VALS: '
    print vals
    print '=== UID: '
    print uid
    print ''
    print ''

    context = context or {}

    # is the create coming from a sync or import? If yes, apply rules from msf_access_right module
    # TODO: remove the testing lines below
    context['sync_data'] = True
    real_uid = uid
    uid = 0
    if uid != 1 and context.get('sync_data'):
        uid = real_uid

        print '====== SYNCING'

        # create the record. we will sanitize it later based on domain search check
        create_result = super_create(self, cr, uid, vals, context)

        if create_result:

            instance_level = _get_instance_level(self, cr, uid)

            print '=== INSTANCE_LEVEL: ', instance_level

            if instance_level:

                # get rules for this model
                model_name = self._name
                user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
                groups = [x.id for x in user.groups_id]

                rules_pool = self.pool.get('msf_access_rights.field_access_rule')
                rules_search = rules_pool.search(cr, uid, ['&', ('model_id.name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

                print '=== MODEL: ', model_name
                print '=== USER: ', user
                print '=== GROUPS: ', groups
                print '=== RULES_SEARCH: ', rules_search

                # do we have rules that apply to this user and model?
                if rules_search:

                    print '====== GOT RULES: ', rules_search

                    rules = rules_pool.browse(cr, uid, rules_search)
                    new_values = {}

                    # for each rule, check the record against the rule domain.
                    for rule in rules:

                        print '=== DOMAIN TEXT: ', rule.domain_text

                        # prepare (or skip) the domain check
                        is_match = True

                        if rule.domain_text:
                            is_match = _record_matches_domain(self, cr, uid, create_result, rule.domain_text)
                        
                        print '=== IS_MATCH: ', is_match

                        if is_match:
                            
                            # if record matches the domain, modify new values
                            for line in rule.field_access_rule_line_ids:
                                if not line.value_not_synchronized_on_create:
                                    new_values[line.field.name] = None

                    # If we have any values to update
                    if new_values:

                        # replace None with the class defaults
                        defaults = self.pool.get(model_name)._defaults

                        print '=== NEW VALUES: ', new_values
                        print '=== DEFAULTS: ', defaults

                        for key in defaults.keys():
                            print '...key: ', key
                            if key in new_values:
                                print '......val: ', new_values.get(key)
                                print '......def: ', defaults[key]
                                new_values[key] = defaults[key]

                        print '====== GOT NEW VALUES: ', new_values

                        # then update the record
                        self.write(cr, uid, create_result, new_values, context=context)

                return create_result
            else:
                logging.getLogger(self._name).warn('No instance name defined! Until one has been defined in msf.instance, no Field Access Rules can be respected!')
                return create_result

        else:
            return False

    else:
        return super_create(self, cr, uid, vals, context)

orm.orm.create = create

super_write = orm.orm.write

def write(self, cr, uid, ids, vals, context=None):
    """
    Check if user has write_access for each field in target record with applicable Field Access Rules. If not, throw exception.
    Also if syncing, check if field value should be synced on write, based on Field Access Rules.
    """

    context = context or {}

    real_uid = uid
    uid = 0
    if uid != 1:
        uid = real_uid

        print '================== WRITE OVERRIDE'

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
        rules_search = rules_pool.search(cr, uid, ['&', ('model_id.name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids', '=', False)])

        print '=== INSTANCE_LEVEL: ', instance_level
        print '=== MODEL: ', model_name
        print '=== USER: ', user
        print '=== GROUPS: ', groups
        print '=== RULES_SEARCH: ', rules_search
        print '=== IDS: ', ids

        # if have rules
        if rules_search:

            rules = rules_pool.browse(cr, uid, rules_search, context=context)
            current_records = self.browse(cr, uid, ids, context=context)

            # check for denied write_access. Loop through current_records and check it against each rule's domain, then search for access denied fields. throw exception if found
            for record in current_records:
                for rule in rules:
                    if _record_matches_domain(self, cr, uid, record.id, rule.domain_text):

                        # rule applies for this record so throw exception if we are trying to edit a field without write_access
                        access_denied_fields = [line for line in rule.field_access_rule_line_ids if not line.write_access and line.field.name in vals]
                        if access_denied_fields:
                            print '=== ACCESS_DENIED_FIELDS: ', access_denied_fields
                            raise osv.except_osv('Access Denied', 'You are trying to edit a value that you don\' have access to edit')

            # if syncing, sanitize editted rows that don't have sync_on_write permission
            if context.get('sync_data'):

                print '====== SYNCING'

                # iterate over current records and look for rules that match it
                for record in current_records:
                    new_values = copy.deepcopy(vals)

                    for rule in rules:
                        if _record_matches_domain(self, cr, uid, record.id, rule.domain_text):

                            print '=== RULE MATCHES: ', rule.id

                            # rule applies for this record so delete key from new values if key is value_not_synchronized_on_write and the value is different from the existing record field
                            no_sync_fields = [line for line in rule.field_access_rule_line_ids if line.value_not_synchronized_on_write and line.field.name in vals and hasattr(record, line.field.name) and vals[line.field.name] != getattr(record, line.field.name)]

                            for line in no_sync_fields:
                                del new_values[line.field.name]

                    if len(new_values) != len(vals):
                        print '=== REMOVED KEYS..'
                        print list(set(vals) - set(new_values))

                    super_write(self, cr, uid, ids, new_values, context=context)

                return True

        else:
            return super_write(self, cr, uid, ids, vals, context=context)

    else:
        return super_write(self, cr, uid, ids, vals, context=context)

orm.orm.write = write