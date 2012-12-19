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

from osv import orm
import logging

super_create = orm.orm.create

def _get_instance_level(self, cr, uid):
    instance_pool = self.pool.get('msf.instance')
    instance_level_search = instance_pool.search(cr, uid, [('level','!=',False)])
    instance_level = instance_pool.browse(cr, uid, instance_level_search[0]).level

    if instance_level == 'section':
        instance_level = 'hq'

    return instance_level.lower()

def create(self, cr, uid, vals, context=None):
    """
    If rules defined for current user and model, create each record then check domain for each record.
    If domain matches, for each field without write_access in the rule, update created field with default values.
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
    uid = 0
    if uid != 1 and context.get('sync_data'):
        uid = 1

        print '====== SYNCHING'

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
                rules_search = rules_pool.search(cr, uid, ['&', ('model_id.name', '=', model_name), ('instance_level', '=', instance_level), '|', ('group_ids', 'in', groups), ('group_ids','=',False)])

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
                            domain = eval(rule.domain_text)
                            domain.append(('id','=',create_result))
                            domain.append('&')
                            domain.reverse()

                            print '=== DOMAIN: ', domain

                            if not self.search(cr, uid, domain, context=context):
                                is_match = False

                            print '=== IS_MATCH: ', is_match
                            
                        # if record is found that means it matches the domain so modify new values
                        for line in rule.field_access_rule_line_ids:
                            if not line.write_access:
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
                logging.getLogger(self._name).warn('No instance name defined! Until one has been defined in msf.profile, no Field Access Rules can be respected!')
                return create_result

        else:
            return False
            
    else:
        return super_create(self, cr, uid, vals, context)

orm.orm.create = create