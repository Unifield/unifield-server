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

super_fields_view_get = orm.orm.fields_view_get

def button_fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
    """
    Dynamically change button groups based on button access rules
    """

    context = context or {}
    fields_view = super_fields_view_get(self, cr, uid, view_id, view_type, context, toolbar, submenu)

    if uid != 1:

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
                for rule in [rule for rule in rules if rule.getattr('name', False) == button_name]:
                    if rule.group_ids:
                        if button.attrib.get('groups', False):
                            # append to existing
                            existing_groups = button.attrib.get('groups','[]')
                            button.attrib.set('groups', str(eval(existing_groups) + eval(rule.group_ids)))
                        else:
                            # create groups tag
                            button.attrib.set('groups', str(rule.group_ids))
                
            fields_view['arch'] = etree.tostring(view_xml)
            
            return fields_view

        else:
            return fields_view

    else:
        return fields_view

orm.orm.fields_view_get = button_fields_view_get

