# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
{
    "name" : "Button Access Rights for MSF",
    "version": "1.0",
    "author" : "OpenERP",
    "developer": "Max Mumford",
    "category" : "Generic Modules/Others",
    "depends" : ['base'],
    "description": """Provides functionality to define access rights  
    for buttons in views based and the actions and workflows they trigger
    """,
    "update_xml": [
        'views/view_config_view.xml',
        'views/button_access_rule_view.xml',
        'views/ir_ui_view_view.xml',
        'menu/button_access_rules.xml',
        'menu/view_config.xml',
        'data/groups.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
