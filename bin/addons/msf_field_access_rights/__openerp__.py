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
    "name" : "Field Access Rights for MSF",
    "version": "1.0",
    "author" : "OpenERP",
    "developer": "Max Mumford",
    "category" : "Generic Modules/Others",
    "description": """Provides functionality to define access rights and 
    synchronization propagation settings concerning the MSF synchronization 
    server hierarchy for models and specific fields of models.
    """,
    "update_xml": [
        'views/field_access_rule_view.xml',
        'views/field_access_rule_line_view.xml',
        'views/view_model_fields_tree.xml',
        'menu/menu.xml',
        'data/groups.xml',
        'security/ir.model.access.csv',
    ],
    "test": [
    ],
    "depends": [
        'msf_instance',
    ],
    'active': False,
    'installable': True,
    #    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
