# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
    "name" : "Analytic Account for MSF",
    "version": "1.1",
    "author" : "MSF: Matthieu Dietrich",
    "category" : "Generic Modules/Projects & Services",
    "depends" : ["analytic", "account", "account_analytic_plans"],
    "description": """Module for defining analytic accounting object.
    """,
    "init_xml" : [
        'data/analytic_account_data.xml',
    ],
    "update_xml": [
        'analytic_account_activable_view.xml',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'active': False,
#    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
